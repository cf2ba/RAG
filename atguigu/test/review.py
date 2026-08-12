# atguigu/query_process/nodes/node_item_name_confirm.py





import json

from langchain.chat_models import init_chat_model

from atguigu.config.config import MilvusConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybrid
from atguigu.tool.mongodb import get_recent_history_list, add_or_update_history, collection, update_item_names_and_query


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心商品名称。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        #先拿到会话id
        session_id = state.get("session_id")
        if not session_id:
            raise ValueError("会话id不存在")
        original_query = state.get("original_query")
        if not original_query:
            raise ValueError("没有提问")
        #如果有问题，则需要更新历史记录
        message_id = add_or_update_history(session_id=session_id,role="user",rewritten_query=original_query)
        #根据会话id获取当前几条历史对话
        history_list = get_recent_history_list(session_id=session_id,limit=10)
        #拿到后进行进行拼接
        history_content = ''
        for history in history_list:
            role=history.get("role")
            text =history.get("text")
            content=f"{role}{text}\n"
            history_content += content


        #构建大模型
        llm = init_chat_model()
        messages = []
        res = llm.invoke(messages)

        res_json= res.content
        #它是一个代码框对齐进行替换
        if res_json.startswith("```json"):
            res_json = res_json.replace("```json","").replace("'''","")
        #对其进行反序列化
        res_dict=json.loads(res_json)
        #反序列化后可以拿到item_names 和rewritten_query
        item_names = res_dict.get("item_names")
        if item_names:
            for item_name in item_names:
                item_name = item_name.replace("\n",'').replace("\t","").replace(" ",'')
        else:
            item_names = []

        rewritten_query = res_dict.get("rewritten_query")
        if not rewritten_query:
            rewritten_query=original_query

        collection_name = MilvusConfig.item_name_collection
        final_item_name = []
        #下一步就是向量化大模型识别的主题和milvus中已经存库的rag外挂文件的主题进行混合检索得到向量化评分
        for idx,item_name in enumerate(item_names):
            embeddings = get_bge_m3_embedding(item_name)
            reqs = create_reqs(
                dense_data=embeddings.get("dense")[idx],
                sparse_data=embeddings.get("sparse")[idx],
                dense_anns_field="dense_vector",
                sparse_anns_field="sparse_vector",
                limit=10
            )
            #混合检索
            res = search_hybrid(
                collection_name=collection_name,
                reqs=reqs,
                ranker=(0.8,0.2),
                limit=10,
                output_fields=[item_name]
            )
            print(res)
            print(res[0])
            #混合检索后对结果进行整理
            for item in res[0]:
                search_result={
                    "original_item_name":item_name,
                    "search_item_name":item.get("entity").get("item_name"),
                    "score":item.get("distance")
                }
                final_item_name.extend(search_result)
        #接下来更具向量化分数进行标准化对齐
        confirm_item_name = [
            final_item.get("item_name")
            for final_item in final_item_name
        if final_item.get("score") >=0.85
        ]
        option_item_name = [
            final_item.get("item_name") for final_item in final_item_name if final_item.get("score") > 0.6
        ]

        if confirm_item_name:
            #回填的内容
            answer=""
            final_item_name=confirm_item_name
        elif option_item_name:
            answer=f"请确定你要咨询的商品是哪些{",".join(option_item_name)}"
            final_item_name=[]
        else:
            answer=f"无法识别你要咨询哪个产品，请重新提问"
            final_item_name=[]

    #下一步就是要进行根据是否有回答 ，更新会话历史记录，同时增量更新 根据ids进行更新
        if answer:
            message_id=add_or_update_history(session_id,"assistant",rewritten_query)
        history_list=get_recent_history_list(session_id,limit=10)
        ids = [history.get("_id") for history in history_list]
        if ids:
            update_item_names_and_query(ids,final_item_name,rewritten_query)










        logger.info(f"【{self.name}】节点逻辑")

        return state

if __name__ == '__main__':
    node = NodeItemNameConfirm()
    init_state = {
        "session_id":"test001",
        "original_query":"是什么"
    }
    res = node(init_state)
    logger.info(json_format_tool(res))