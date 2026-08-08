# atguigu/import_process/nodes/node_item_name_recognition.py
import json
from typing import Any

from langchain.chat_models import init_chat_model
from pymilvus import DataType, MilvusClient

from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client
from atguigu.tool.prompt import ITEM_NAME_SYSTEM_PROMPT, ITEM_NAME_USER_PROMPT_TEMPLATE


# from langsmith.schemas import DataType


class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    链路作用：
    1. 从图状态中读取文档切片chunks、文档标题
    2. 截取前N个切片拼接上下文（做长度截断防止LLM超限）
    3. 调用大模型识别文档核心主体名称（商品/产品名称item_name）
    4. Milvus向量库幂等写入主体名称稠密+稀疏双向量
    5. 将识别出的item_name回填到所有切片chunk中，更新流程图状态
    """

    name = "node_item_name_recognition"

    def get_chunks(self, state: ImportGraphState) -> tuple[list, str]:
        """
        从流程图State中获取切片列表与文档标题，并做非空强校验
        :param state: LangGraph流转状态对象
        :return: chunks切片列表, file_title文档标题
        """
        chunks = state.get("chunks", '')
        file_title = state.get("file_title")
        # 切片为空直接抛出异常，后续无法做主体识别
        if not chunks:
            logger.error("chunks为空必须有值才能进行主体识别")
            raise Exception("chunk是空的，必须有值才能进行主题识别")
        # 文档标题缺失报错
        if not file_title:
            logger.error("file_title是空的")
            raise Exception("file_title是空的")
        return chunks, file_title

    def get_chunks_content(self, chunks: list[Any], file_title: str) -> str:
        """
        截取前10个文档切片，拼接LLM识别用上下文文本，超长截断至1000字符
        拼接格式：[切片序号] + 文档总标题 + 切片小标题 + 切片正文
        :param chunks: 全量文档切片数组
        :param file_title: 文档顶层标题
        :return: 拼接后的上下文字符串（长度上限1000）
        """
        # 只取前10个切片用于LLM识别，减少上下文冗余
        chunk_k_list = chunks[:10]
        max_len = 1000  # 上下文最大字符限制，防止LLM上下文溢出
        content_str = '\n'
        # 遍历切片拼接文本
        for idx, chunk in enumerate(chunk_k_list, start=1):
            title = chunk.get("title")
            content = chunk.get("content")
            # 单条切片结构化拼接
            chunk_str = f"[切片{idx}]\n{file_title}\n{title}\n{content}"
            content_str += chunk_str
            # 到达长度阈值直接终止拼接
            if len(content_str) > max_len:
                logger.info(f"已经超过最大长度，不再拼接")
                break
        # 强制截断到最大长度，兜底防护
        content_str = content_str[:max_len]
        return content_str

    def get_item_name(self, content_str: str, file_title: str) -> Any:
        """
        调用LLM基于文档上下文识别核心主体名称（产品/商品名）
        模型返回值做空白字符清洗，识别失败则降级使用文档标题作为主体名
        :param content_str: 切片拼接上下文
        :param file_title: 文档标题（兜底备用）
        :return: 清洗后的主体名称item_name
        """
        # 初始化LLM对话模型，使用配置文件参数
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base_url,
            temperature=LLMConfig.llm_default_temperature
        )
        # 组装系统提示词+用户提示词
        messages = [
            {"role": "system", "content": ITEM_NAME_SYSTEM_PROMPT},
            {"role": "user",
             "content": ITEM_NAME_USER_PROMPT_TEMPLATE.format(file_title=file_title, context=content_str)},

        ]
        # 调用模型推理
        result = llm.invoke(input=messages)
        item_name = result.content
        # 清洗换行、空格、制表符，规整主体名称格式
        item_name = item_name.replace(" ", "").replace("\n", "").replace("\t", "")
        print(item_name)
        # 模型识别结果为空，降级使用文档标题
        if not item_name:
            logger.warning("LLM主体名称识别为空，使用文档标题兜底")
            item_name = file_title
        return item_name

    def get_collection(self) -> tuple[str, MilvusClient]:
        """
        初始化Milvus客户端，校验主体名称向量集合是否存在
        不存在则自动创建集合结构+稠密向量/稀疏向量双索引
        :return: 集合名称collection_name, Milvus客户端实例
        """
        milvus_client = get_milvus_client()
        if not milvus_client:
            logger.error("初始化milvus_client失败")
            raise Exception("初始化milvus_client失败")
        collection_name = MilvusConfig.item_name_collection
        # 集合不存在执行建表逻辑
        if not milvus_client.has_collection(collection_name):
            # 创建Schema，主键自增
            schema = milvus_client.create_schema(auto_id=True)
            schema.add_field(
                field_name="item_name_id",
                datatype=DataType.INT64,
                is_primary=True
            ).add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="file_title",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=1024  # BGE-M3稠密向量维度1024
            ).add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR
            )
            # 构建索引参数
            index_params = milvus_client.prepare_index_params()
            # 稠密向量索引：IVF_FLAT聚类索引，余弦相似度匹配
            index_params.add_index(
                field_name="dense_vector",
                index_type="IVF_FLAT",
                metric_type='COSINE',
                params={'nlist': 128, "nprobe": 10}
            )
            # 稀疏向量倒排索引，内积相似度
            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",
                params={
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "normalize": True,
                    "quantization": "none"
                }
            )
            # 创建Milvus集合
            milvus_client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params
            )
        # 【BUG修复】原返回顺序颠倒：(collection_name, milvus_client)
        return collection_name, milvus_client

    def insert_data_back(self, chunks: list[Any], collection_name: str, file_title: str, item_name,
                         milvus_client: MilvusClient) -> list[Any]:
        """
        Milvus幂等写入主体名称向量：先删除同名历史数据，再新增向量记录
        完成后将item_name回填到全部切片chunk中返回
        :param chunks: 原始文档切片列表
        :param collection_name: Milvus集合名
        :param file_title: 文档标题
        :param item_name: 识别出的主体名称
        :param milvus_client: Milvus客户端实例
        :return: 全部回填item_name后的chunks数组
        """
        # 加载集合，必须加载才能执行删除/插入操作
        milvus_client.load_collection(collection_name=collection_name)
        # SQL注入防护：转义反斜杠、单引号、双引号，防止filter语法报错
        safe_item_name = item_name.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        filter_str = f"item_name=='{safe_item_name}'"
        # 幂等删除：删除库中相同主体名称的旧数据
        milvus_client.delete(collection_name=collection_name, filter=filter_str)

        # 使用BGE-M3生成主体名称稠密+稀疏双向量
        embedding = get_bge_m3_embedding([item_name])
        # 组装入库结构体
        data = {
            "item_name": item_name,
            "file_title": file_title,
            "dense_vector": embedding.get("dense")[0],
            "sparse_vector": embedding.get("sparse")[0]
        }
        # 向量数据插入Milvus
        milvus_client.insert(
            collection_name=collection_name,
            data=data
        )
        # 给每一个切片都打上主体名称标签
        for chunk in chunks:
            chunk["item_name"] = item_name
        # 【BUG修复】原代码只return最后一个chunk，改为返回完整chunks列表
        return chunks

    def process(self, state: ImportGraphState):
        """
        LangGraph节点主执行入口，重写NodeBase.process
        完整流程：参数校验→上下文拼接→LLM主体识别→Milvus幂等入库→切片字段回填→输出图状态
        :param state: 上游传入的流程图状态
        :return: 更新后的状态字典：item_name主体名、带标签的chunks
        """
        chunks, file_title = self.get_chunks(state)
        # 截取切片拼接LLM上下文
        content_str = self.get_chunks_content(chunks, file_title)
        # LLM识别产品/主体名称
        item_name = self.get_item_name(content_str, file_title)
        # 获取Milvus集合与客户端并创建表
        collection_name, milvus_client = self.get_collection()
        # 向量入库+chunks字段回填
        chunks = self.insert_data_back(chunks, collection_name, file_title, item_name, milvus_client)
        # 输出更新后的状态，流转给下游节点
        return {
            "item_name": item_name,
            "chunks": chunks
        }



if __name__ == '__main__':
    # 本地单元测试入口
    node = NodeItemNameRecognition()
    # 加载本地切片JSON文件
    with open(r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)
    # 构造测试State
    init_state = {
        "chunks": chunks,
        "file_title": "hak180产品安全手册_new",
    }
    # 执行节点逻辑
    result = node(init_state)
    # 格式化打印执行结果
    logger.info(json_format_tool(result))
    with open(r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\item_name_embedding.json", "w",
              encoding="utf-8") as f:
        f.write(json_format_tool(result['chunks']))