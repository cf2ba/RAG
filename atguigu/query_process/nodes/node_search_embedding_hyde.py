# atguigu/query_process/nodes/node_search_embedding_hyde.py
import json
from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybrid, get_chunks_collection
from atguigu.tool.prompt import HYDE_PROMPT


class NodeSearchEmbeddingHyde(NodeBase):
    """
    节点功能：HyDE (Hypothetical Document Embedding) 假设文档嵌入检索节点
    执行流程：
        1. 从工作流状态获取改写后的查询语句与业务过滤item_name列表
        2. 调用大模型基于用户问题生成一段假设性标准答案（虚拟文档）
        3. 将【原始改写query + LLM生成的假设答案】拼接为合并查询文本
        4. 使用BGE-M3生成稠密向量+稀疏向量
        5. 构建Milvus混合检索请求，附带item_name标量过滤条件
        6. 执行稠密+稀疏混合检索，融合打分召回文本块
        7. 格式化检索结果写入状态，供后续节点使用
    作用原理：直接使用用户问句向量检索效果有限；LLM生成和答案风格一致的虚拟文档再向量化，
    向量空间上更贴近知识库内真实段落，显著提升向量召回相关性。
    """

    # 覆盖基类的 name 属性，标识当前LangGraph工作流节点唯一名称
    name: str = "node_search_embedding_hyde"

    def process(self, state: QueryGraphState):
        """
        节点核心处理逻辑，LangGraph标准节点执行入口
        :param state: 工作流全局状态对象，承载上下游节点传递的所有数据
        :return: dict 更新的状态字段，LangGraph自动合并至全局state
        """

        # 1. 获取上游生成的改写后查询语句
        rewritten_query = state.get("rewritten_query", '')
        # 校验改写查询不能为空，缺少该参数无法执行HyDE流程
        if not rewritten_query:
            logger.error("不存在rewritten_query")
            raise Exception("不存在rewritten_query")

        # 2. 获取业务过滤标识列表 item_names，用于Milvus标量过滤
        item_names = state.get("item_names", '')
        if not item_names:
            logger.error("不存在item_name")
            raise ValueError("不存在item_name")

        # 3. 初始化LLM客户端，用于生成HyDE假设性文档
        llm = init_chat_model(
            model=LLMConfig.llm_default_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base_url,
            temperature=LLMConfig.llm_default_temperature
        )
        # 构造对话消息（当前仅传入用户问题，缺少prompt模板，为原有代码逻辑保留）
        messages = [
            {"role": "user", "content": HYDE_PROMPT.format(rewritten_query=rewritten_query)}
        ]
        # 调用大模型生成假设答案
        res = llm.invoke(messages)
        # print(res.content)
        hyde_answer = res.content

        # HyDE核心：原始改写查询拼接LLM生成的虚拟答案作为向量化输入文本
        merged_query = f"{rewritten_query}{hyde_answer}"

        # 4. 调用BGE-M3服务，生成稠密向量dense、稀疏向量sparse
        embeddings = get_bge_m3_embedding([merged_query])
        # 读取配置中存储文档块的Milvus集合名称
        collection_name = get_chunks_collection()

        # 5. 转义item_names内部特殊字符，防止构建Milvus表达式时出现引号语法报错
        # item_names = [item.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        #               for item in item_names
        #               ]
        # 构造Milvus标量过滤表达式：限定只检索指定item_name范围内的数据
        expr = f"item_name in {json.dumps(item_names,ensure_ascii=False)}"  # Milvus要求in后紧跟JSON数组字符串
        # 附加内容类型过滤（景点介绍/线路推荐/酒店信息/美食推荐/交通指南等）
        content_types = state.get("content_types") or []
        if content_types:
            expr += f" and content_type in {json.dumps(content_types, ensure_ascii=False)}"

        # 6. 组装混合检索请求参数：稠密向量、稀疏向量、对应索引字段、召回条数、过滤条件
        reqs = create_reqs(
            dense_data=embeddings.get("dense")[0],
            sparse_data=embeddings.get("sparse")[0],
            dense_anns_field="dense_vector",
            sparse_anns_field="sparse_vector",
            limit=10,
            expr=expr
        )
        # 执行Milvus稠密+稀疏混合检索；ranker=(稠密权重0.8,稀疏权重0.2)融合打分
        res = search_hybrid(
            collection_name=collection_name,
            reqs=reqs,
            ranker=(0.8, 0.2),
            limit=10,
            output_fields=["id", "file_title", "title", "content", "item_name", "region", "content_type", "doc_name", "topics", "source_url"]
        )

        # 7. 格式化Milvus返回结果，统一结构：把entity字段展开，增加相似度score与数据源标记
        hyde_embedding_chunks = [
            {
                **item.get("entity"),       # 取出数据库存储的业务字段
                "score": item.get("distance"),  # 检索相似度分数
                "source": "local"               # 标记数据源为本地知识库Milvus
            }
            for item in res[0]
        ]

        # logger.info(json_format_tool(hyde_embeddings_chunks))

        # 返回状态更新字典，写入hyde_embeddings_chunks，传递给下游节点
        return {
            "hyde_embedding_chunks": hyde_embedding_chunks
        }

        # TODO 原有遗留注释，原样保留
        # logger.info(f"【{self.name}】节点逻辑")
        # return state
        # return {"hyde_embedding_chunks": []}


if __name__ == '__main__':
    """
    节点本地独立调试入口
    直接运行当前文件可单独测试HyDE检索节点，不启动完整工作流
    """
    node = NodeSearchEmbeddingHyde()
    # 构造模拟上游传入的state测试数据
    init_state = {
        "rewritten_query": "关于BrotherHAK180烫金机如何使用",
        "item_names": ["BrotherHAK180烫金机"]
    }
    # 执行节点处理函数
    result = node(init_state)
    # 打印格式化后的运行结果
    logger.info(json_format_tool(result))