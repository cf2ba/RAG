# atguigu/query_process/nodes/node_item_name_confirm.py

import json
from typing import Any

from langchain.chat_models import init_chat_model
from transformers.integrations import rewrite_logs

from atguigu.config.config import LLMConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client, create_reqs, search_hybrid, get_item_name_collection
from atguigu.tool.mongodb import add_or_update_history, get_recent_history_list, update_item_names_and_query
from atguigu.tool.prompt import ITEM_NAME_EXTRACT_SYSTEM_PROMPT, ITEM_NAME_EXTRACT_TEMPLATE


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心商品名称。
    整体流程：
    1. 获取会话历史、当前用户提问，写入mongodb对话历史
    2. 拼接上下文历史交给LLM提取商品名称 + 重写用户原始query
    3. 使用BGE-M3对提取出的商品名称生成稠密/稀疏向量
    4. 在Milvus商品名称向量库执行混合检索匹配标准商品名
    5. 根据相似度阈值判定：直接确认商品 / 向用户发起候选确认 / 识别失败
    6. 更新mongodb历史记录，回填识别到的商品名与改写后的query，输出状态
    """
    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    # 主体名称对齐阈值：混合检索返回的相似度分数
    # >= CONFIRM 直接确认；OPTION~CONFIRM 弹出候选让用户选；< OPTION 视为无法识别
    CONFIRM_SCORE_THRESHOLD = 0.8   # 原 0.85 过严，导致“直接确认”永远触发不了
    OPTION_SCORE_THRESHOLD = 0.5    # 原 0.6 略严，容易误判为“无法识别”

    def get_history_contetn(self, state: QueryGraphState) -> tuple[str, str, str, Any]:
        """
        从图状态中读取session_id、原始query，写入对话历史；加载最近会话上下文
        :param state: 查询工作流状态对象
        :return: history_content:拼接后的会话上下文文本, message_id:本次用户消息id, original_query:用户原始提问, session_id:会话唯一标识
        """
        session_id = state.get("session_id")
        if not session_id:
            logger.error("session_id必须传递")
            raise ValueError("session_id必须传递")
        original_query = state.get("original_query")
        if not original_query:
            logger.error("必须传入问题")
            raise ValueError("必须传入问题")

        # 拿到session_id和original_query代表这一次提问可以添加到历史记录中
        message_id = add_or_update_history(session_id, "user", original_query)
        # print(message_id)
        # 从历史记录中获取最近的十条，把内容拼接成一个大串，然后让大模型根据这个大串帮我们识别主题名字，及修改原始问题
        history_list = get_recent_history_list(session_id, limit=10)
        history_content = ""
        for history in history_list:
            role = history.get("role")
            text = history.get("text")
            content = f"{role}:{text}\n"
            history_content += content
        print(history_content)
        return history_content, message_id, original_query, session_id
    def llm_get_item_name_rewritten_query(self, history_content: str, original_query: str) -> tuple[list[Any], list[Any], Any]:
        """
        调用大模型，结合会话上下文提取目的地/景区/线路名称、内容类型并重写用户query；处理LLM返回markdown格式JSON
        :param history_content:拼接好的会话上下文
        :param original_query:用户原始提问
        :return: item_names:LLM识别出的目的地/景区/线路列表, content_types:内容类型列表, rewritten_query:大模型优化重写后的查询语句
        """
        # 整理完数据，准备调用大模型识别主题和问题重写
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base_url,
            temperature=LLMConfig.llm_default_temperature
        )
        messages = [
            {"role": "system", "content": ITEM_NAME_EXTRACT_SYSTEM_PROMPT},
            {"role": "user",
             "content": ITEM_NAME_EXTRACT_TEMPLATE.format(history_text=history_content, original_query=original_query)},
        ]
        res = llm.invoke(input=messages)
        print(res.content)
        # 对大模型输出的返回信息进行整理和判断 对主题名如果存在进行去除空格等整理，不存在返回一个空列表
        res_json = res.content
        # 大模型在返回json的时候有概率输出一个json的md代码块，此时要把json的``` ```去掉
        if res_json.startswith("```json"):
            res_json = res_json.replace("```json", "").replace("```", "")
        # 把json转化为字典（反序列化）取出item_names，判断如果有值，对item_names去除一下空白
        res_dict = json.loads(res_json)
        item_names = res_dict.get("item_names")
        content_types = res_dict.get("content_types")
        rewritten_query = res_dict.get("rewritten_query")
        if item_names:
            item_names = [
                item_name.replace(" ", "").replace("\n", "").replace("\t", "")
                for item_name in item_names]
        else:
            item_names = []

        if content_types:
            content_types = [
                content_type.replace(" ", "").replace("\n", "").replace("\t", "")
                for content_type in content_types]
        else:
            content_types = []

        if not rewritten_query:
            rewritten_query = original_query
        return item_names, content_types, rewritten_query

    def get_embedding_hybrid_score(self, item_names: list[Any]) -> list[Any]:
        """
        使用BGE-M3向量化商品名称，调用Milvus执行稠密+稀疏混合检索，组装检索结果列表
        :param item_names: LLM提取出来的待匹配商品名称列表
        :return: final_search_item_names: 每条包含原始名称、库内匹配商品名、相似度分数的结果集合
        """
        # 对整个item_names进行向量化，再对每个item_name进行混合搜索
        embeddings = get_bge_m3_embedding(item_names)

        collection_name = get_item_name_collection()

        final_search_item_names = []
        for idx, item_name in enumerate(item_names):
            dense_data = embeddings.get("dense")[idx]
            sparse_data = embeddings.get("sparse")[idx]
            # 混合搜索 创建reqs 调用工具 传入参数
            reqs = create_reqs(dense_data=dense_data,
                               sparse_data=sparse_data,
                               dense_anns_field="dense_vector",
                               sparse_anns_field="sparse_vector")
            res = search_hybrid(
                collection_name=collection_name,
                reqs=reqs,
                ranker=(0.8, 0.2),
                limit=10,
                output_fields=["item_name"]
            )
            print(json_format_tool(res))
            print(res[0])
            search_item_names = [
                {
                    "original_item_name": item_name,
                    "search_item_name": item.get("entity", {}).get("item_name", ""),
                    "score": item.get("distance")
                }
                for item in res[0]
            ]

            # extend和append的区别: append是把整体直接放进列表，形成二维嵌套
            # eg: list1 = [1,2,3] list1.append([5,6]) 结果是【1，2，3，【5，6】】
            # 如果是extend list1 = [1,2,3] list1.extend([5,6]) 结果是【1，2，3，5，6】
            final_search_item_names.extend(search_item_names)
        print(final_search_item_names)
        return final_search_item_names

    def align_item_names(self, answer: str, final_item_names: list[Any], final_search_item_names: list[Any]) -> tuple[str, list[Any]]:
        """
        根据Milvus检索相似度阈值做商品名称对齐逻辑，生成回复话术与最终确认商品列表
        阈值规则：>=0.85 直接确认；0.6<=score<0.85 弹出候选让用户选择；<0.6 识别失败
        :param answer: 初始回复文本
        :param final_item_names: 输出最终确认商品列表
        :param final_search_item_names: Milvus混合检索返回全部匹配结果
        :return: answer:对外输出话术, final_item_names:经过相似度筛选后的标准商品名称列表
        """
        # 找分数最高的进行对齐，通过分数确认最终确认的主题或者候选的主题
        # 根据搜索置信度（score）
        # 打印每一条检索结果的分数，便于排查“为什么总是问哪一个/无法识别”
        for item in final_search_item_names:
            logger.info(
                f"主体对齐 score={item.get('score')} 用户说[{item.get('original_item_name')}] "
                f"库内命中[{item.get('search_item_name')}]"
            )

        confirm_item_names = [
            item.get("search_item_name")
            for item in final_search_item_names
            if item.get("score") >= self.CONFIRM_SCORE_THRESHOLD
            # 用户（或LLM）说出的名字与库内名字完全一致时，直接确认，
            # 不再受分数阈值卡住，避免“选完还问去哪”的死循环
            or item.get("original_item_name") == item.get("search_item_name")
        ]
        option_item_names = [
            item.get("search_item_name")
            for item in final_search_item_names
            if item.get("score") >= self.OPTION_SCORE_THRESHOLD
        ]

        if confirm_item_names:
            final_item_names = confirm_item_names
            answer = ''
        elif option_item_names:
            final_item_names = []
            answer = f"请确认你要咨询的目的地/景区是这些的哪一个？{','.join(option_item_names)}"
        else:
            final_item_names = []
            answer = f"对不起，无法识别你要咨询的目的地/景区，请重新提问"
        return answer, final_item_names

    def handler_history(self, answer: str, final_item_names: list[Any], item_names: list[Any], message_id: str | Any,
                        original_query: str, rewritten_query, session_id) -> dict[str, str | list[Any] | Any]:
        """
        统一处理对话历史：存在回复话术则写入assistant消息；批量更新历史对话里的商品名与重写query，组装节点输出结果
        :param answer:对齐后生成的回复话术
        :param final_item_names:相似度筛选后标准商品名
        :param item_names:LLM初次提取商品名
        :param message_id:当前用户消息id
        :param original_query:用户原始提问
        :param rewritten_query:LLM重写后的query
        :param session_id:会话ID
        :return: 组装完成的字典，作为节点输出传递给工作流state
        """
        # 判断answer 有没有值来处理历史记录
        # 如果answer有值,代表需要新增助手回复消息
        # 不管有没有answer，我们都要给历史记录回填item_names和rewritten_query
        if answer:
            message_id = add_or_update_history(session_id, "assistant", answer)

        # 回填数据给历史记录最近的n条对话
        # 如果有answer,我们回填的是final_item_names
        history_list = get_recent_history_list(session_id, limit=10)
        print(history_list)
        ids = [history.get("_id") for history in history_list]
        if ids:
            update_item_names_and_query(ids, final_item_names, rewritten_query)
        return message_id


    def process(self, state: QueryGraphState):
        """
        节点主执行逻辑，LangGraph节点入口
        :param state: 工作流状态对象
        :return: 更新后的状态字典，传递给后续图节点
        """
        # 第一大步：获取state当中的session_id和original_query，然后根据sessionid获取最近的10条记录整理成大串
        history_content, message_id, original_query, session_id = self.get_history_contetn(state)
        # 第二大步：根据大串调用大模型进行意图识别，获取到意图识别出来的item_names（目的地/景区/线路）、content_types和rewritten_query
        item_names, content_types, rewritten_query = self.llm_get_item_name_rewritten_query(history_content, original_query)

        #拿到了item_names和rewritten_query，接下来需要把item_name进行向量化
        #与milvus中的item_name表中进行混合检索，
        #看看能不能找到相似度高的item_name,如果找到了，最终的item_name才有可能确定下来
        #准备milvus混合检索，所以先去把混合检索的工具定义好
        answer = ""
        final_item_names = []

        if item_names:
            # 第三大步：对item_names进行向量化，然后去milvus中进行混合检索，整理成字典列表final_search_item_names
            final_search_item_names = self.get_embedding_hybrid_score(item_names)
            # 第四大步：根据final_search_item_names的分数来确定最终的确认名字或者候选的名字，对齐名字及设置最终的answer和最终的item_names
            answer, final_item_names = self.align_item_names(answer, final_item_names, final_search_item_names)
        # 第五大步：根据最终的answer来处理更新历史记录
        message_id = self.handler_history(answer, final_item_names, item_names, message_id, original_query,
                                        rewritten_query, session_id)

        return {
            "message_id": message_id,
            "original_query": original_query,
            "answer": answer,
            "item_names": final_item_names,
            "content_types": content_types,
            "rewritten_query": rewritten_query,
            "history": get_recent_history_list(session_id, limit=10)
        }

        # logger.info(f"【{self.name}】节点逻辑")


if __name__ == '__main__':
    """
    模块入口，本地单元测试模拟会话执行当前节点
    """
    #模拟历史会话
    # 模拟会话历史
    session_id = "test_001"
    add_or_update_history(session_id, "user", "咨询下烫金机。")
    add_or_update_history(session_id, "assistant", "您好。请问是哪个型号")
    add_or_update_history(session_id, "user", "hak180")
    add_or_update_history(session_id, "assistant", "具体有什么问题呢？")
    node = NodeItemNameConfirm()
    init_state = {
        "session_id":"test_001",
        "original_query":"咋用"
    }
    result = node(init_state)
    logger.info(json_format_tool(result))