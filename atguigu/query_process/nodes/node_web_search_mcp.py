# atguigu/query_process/nodes/node_web_search_mcp.py
import asyncio
import json

from agents.mcp import MCPServerStreamableHttp

from atguigu.config.config import McpConfig, LLMConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeWebSearchMcp(NodeBase):
    """
    节点功能：通过MCP协议调用百炼web搜索工具，联网检索补充外部信息
    属于查询工作流图中的搜索节点，使用改写后的query执行网页搜索，格式化搜索结果存入状态
    """

    # 覆盖基类的 name 属性，标识当前图节点名称，用于工作流区分节点
    name: str = "node_web_search_mcp"

    def process(self, state: QueryGraphState):
        """
        节点主执行逻辑，重写基类方法，同步入口封装异步MCP调用
        :param state: 工作流状态对象 QueryGraphState，承载整个查询链路上下文数据
        :return: dict 更新后的状态字段，输出web_search_docs网页检索文档列表，并入全局state
        """

        # 获取经过改写后的检索query，改写后的查询词更适合搜索引擎
        rewritten_query = state.get("rewritten_query", '')
        # 校验查询词非空，缺少检索词无法执行搜索
        if not rewritten_query:
            logger.error("没有rewritten_query")
            raise Exception("没有rewritten_query")

        # 同步环境下启动事件循环，执行异步MCP服务调用
        result = asyncio.run(self.mcp_run(rewritten_query))

        # 解析MCP工具返回结果，提取网页搜索pages数组
        search_data = json.loads(result.content[0].text).get("pages")

        # 格式化搜索结果，统一文档结构，供后续检索/大模型节点消费
        return {
            "web_search_docs": [
                {
                    "title": item.get("title"),    # 网页标题
                    "content": item.get("snippet"), # 网页摘要片段
                    "url": item.get("url"),        # 网页链接地址
                    "source": "web"                # 标记数据来源为网络搜索
                }
                for item in search_data
            ]
        }

    async def mcp_run(self, query, limit=10):
        """
        异步MCP客户端通信方法，建立Streamable HTTP连接调用百炼web搜索工具
        :param query: 待检索的搜索关键词（改写后的query）
        :param limit: 搜索结果数量上限（参数预留，当前硬编码传10）
        :return: MCP工具调用返回原始结果对象
        """
        # 获取MCP服务鉴权token
        token = McpConfig.mcp_api_key
        # 创建MCP Streamable HTTP长连接客户端上下文
        async with MCPServerStreamableHttp(
                name="Streamable HTTP Python Server",
                params={
                    "url": McpConfig.mcp_dashscope_base_url,    # MCP服务接口地址
                    "headers": {"Authorization": f"Bearer {token}"}, # 鉴权请求头
                    "timeout": 10,  # 单次请求超时时间
                },
                cache_tools_list=True,          # 缓存工具列表，避免重复拉取工具清单
                max_retry_attempts=3,            # 调用失败最大重试次数
                client_session_timeout_seconds=30 # 客户端会话超时时长
        ) as server:
            # 调用MCP注册工具 bailian_web_search 百炼网页搜索
            result = await server.call_tool("bailian_web_search", arguments={
                "query": query,   # 搜索关键词
                "count": 10       # 请求返回网页条数
            })
            # 返回原始工具调用结果对象
            return result


if __name__ == '__main__':
    # 模块自测入口：实例化搜索节点
    node = NodeWebSearchMcp()
    # 初始化测试状态，传入改写后的搜索query
    init_state = {
        "rewritten_query": "关于BrotherHAK180烫金机如何使用"
    }
    # 执行节点调用，底层自动执行process方法
    result = node(init_state)
    # 使用格式化工具打印最终输出结果
    logger.info(json_format_tool(result))