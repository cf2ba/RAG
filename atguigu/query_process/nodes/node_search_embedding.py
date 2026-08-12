# atguigu/query_process/nodes/node_search_embedding.py
import json

from atguigu.config.config import MilvusConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybrid


class NodeSearchEmbedding(NodeBase):
    """
    节点功能：基于已确认主体名+改写后的用户问题，执行Milvus向量数据库混合检索
    工作流节点职责：
        1. 从全局状态获取改写后的查询语句、过滤主体名称列表
        2. 调用BGE-M3模型生成稠密向量+稀疏向量
        3. 组装标量过滤条件 item_name IN 主体列表
        4. 发起Milvus稠密+稀疏混合检索
        5. 统一格式化检索结果，写入状态 embeddings_chunks 供下游节点使用
    """

    # 覆盖基类的 name 属性，标识节点名称（LangGraph图中唯一节点标识）
    name: str = "node_search_embedding"

    def process(self, state: QueryGraphState):
        """
        节点核心业务逻辑
        :param state: 工作流全局状态对象 QueryGraphState
        :return: dict 更新后的状态字段，LangGraph会自动合并至全局state
        """
        # 1. 获取状态中改写完成后的用户查询
        rewritten_query = state.get("rewritten_query", '')
        # 校验改写后查询不能为空，为空无法执行向量检索
        if not rewritten_query:
            logger.error("不存在rewritten_query字段内容")
            raise Exception("不存在rewritten_query")

        # 2. 获取过滤使用的主体名称列表 item_names
        item_names = state.get("item_names", '')
        if not item_names:
            logger.error("不存在item_name主体过滤列表")
            raise ValueError("不存在item_name")

        # 3. 调用BGE-M3服务，生成查询文本稠密向量、稀疏向量
        embeddings = get_bge_m3_embedding([rewritten_query])
        # 读取配置，确定Milvus目标文档块集合名称
        collection_name = MilvusConfig.chunks_collection

        # 4. 转义item_name特殊字符，防止构建expr表达式时引号、反斜杠语法报错
        item_names = [
            item.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            for item in item_names
        ]
        # 构建Milvus标量过滤表达式：仅检索匹配item_name的文档块
        # Milvus IN 语法要求列表使用标准json字符串格式
        expr = f"item_name in {json.dumps(item_names)}"

        # 5. 组装混合检索请求参数
        reqs = create_reqs(
            dense_data=embeddings.get("dense")[0],    # 查询稠密向量
            sparse_data=embeddings.get("sparse")[0],  # 查询稀疏向量
            dense_anns_field="dense_vector",          # 集合稠密向量字段名
            sparse_anns_field="sparse_vector",        # 集合稀疏向量字段名
            limit=10,                                 # 单路向量检索返回上限
            expr=expr                                 # 标量过滤条件
        )
        # 6. 执行Milvus稠密+稀疏混合检索，加权融合两路分数
        res = search_hybrid(
            collection_name=collection_name,
            reqs=reqs,
            ranker=(0.8, 0.2),       # 融合权重：稠密0.8，稀疏0.2
            limit=10,                # 混合排序后最终返回top10结果
            output_fields=["content", "id", "file_title", "title", "item_name"]  # 需要返回的文档元数据字段
        )
        # 控制台打印原始检索结果，调试使用
        print(res)
        print(res[0])

        # 7. 格式化Milvus返回结构，统一组装成下游通用chunk格式
        # entity为文档原始字段，distance为混合相似度得分，source标记知识库来源
        embeddings_chunks = [
            {
                **item.get("entity"),
                "score": item.get("distance"),
                "source": "local"
            }
            for item in res[0]
        ]
        # 打印格式化后的检索结果日志
        logger.info(json_format_tool(embeddings_chunks))

        # 返回更新字段，写入全局状态，下游节点读取 embeddings_chunks
        return {
            "embeddings_chunks": embeddings_chunks
        }



if __name__ == '__main__':
    """
    本地单元测试入口：独立运行测试当前检索节点逻辑
    模拟工作流传入state，直接执行节点并打印结果
    """
    node = NodeSearchEmbedding()
    # 模拟工作流初始状态
    init_state = {
        "rewritten_query": "关于BrotherHAK180烫金机如何使用",
        "item_names": ["BrotherHAK180烫金机"]
    }
    # 执行节点调用
    result = node(init_state)
    # 格式化输出执行结果日志
    logger.info(json_format_tool(result))