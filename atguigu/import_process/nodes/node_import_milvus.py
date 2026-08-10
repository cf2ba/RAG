# atguigu/import_process/nodes/node_import_milvus.py
import json
from msilib import schema
from typing import Any

from pymilvus import DataType, MilvusClient

from atguigu.config.config import MilvusConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client


# from langsmith.schemas import DataType


class NodeImportMilvus(NodeBase):
    """
    导入向量库节点：数据持久化
    """

    name = "node_import_milvus"
    def get_chunks(self, state: ImportGraphState) -> tuple[int, Any, list]:
        chunks = state.get("chunks", '')
        if not chunks:
            logger.error("导入向量库节点，数据持久化,未找到chunks")
            raise Exception("导入向量库节点，数据持久化,未找到chunks")
        dense_dim = len(chunks[0].get("dense_vector", ''))
        file_title = chunks[0].get("file_title", '')
        return chunks, dense_dim, file_title

    def create_collection(self, dense_dim) -> tuple[MilvusClient, str | None]:
        collection_name = MilvusConfig.chunks_collection
        milvus_client = get_milvus_client()
        if not milvus_client:
            logger.error("milvus_client客户端初始化失败")
            raise Exception("milvus_client客户端初始化失败")
        if not milvus_client.has_collection(collection_name=collection_name):
            schema = milvus_client.create_schema(auto_id=True)
            schema.add_field(
                field_name="id",
                datatype=DataType.INT64,
                is_primary=True
            ).add_field(
                field_name="file_title",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="title",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="content",
                datatype=DataType.VARCHAR,
                max_length=5000
            ).add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="part",
                datatype=DataType.INT64
            ).add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=dense_dim
            ).add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR,
            )

            index_params = milvus_client.prepare_index_params()
            index_params.add_index(
                field_name="dense_vector",
                index_type="IVF_FLAT",  # 检索类型 （暴力检索（数据量不那么大）/分层导航小世界（数据超大规模使用））
                metric_type='COSINE',
                params={"nlist": 128, "nprobe": 10}
            )
            index_params.add_index(
                field_name='sparse_vector',
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",  # 内积
                params={
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "normalize": True,
                    "quantization": "none"
                }
            )
            milvus_client.create_collection(
                index_params=index_params,
                schema=schema,
                collection_name=collection_name
            )
        return collection_name, milvus_client

    def insert_reback(self, chunks: int, collection_name: MilvusClient, file_title: list[Any],
                      milvus_client: str | None) -> \
            dict[str, int]:
        # 删除数据先加载表
        milvus_client.load_collection(collection_name=collection_name)
        # 幂等性删除file_title重复的记录
        file_title = file_title.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        filter_str = f"file_title == '{file_title}'"
        milvus_client.delete(collection_name=collection_name, filter=filter_str)
        # 插入数据
        res = milvus_client.insert(
            collection_name=collection_name,
            data=chunks
        )
        logger.info(res)
        # 把插入数据返回的id,回填到对应的chunks
        ids = res.get("ids")
        if ids:
            for i, chunk in enumerate(chunks):
                chunk["id"] = ids[i]
        return {
            "chunks": chunks
        }

    def process(self, state: ImportGraphState):
        chunks, dense_dim, file_title = self.get_chunks(state)

        collection_name, milvus_client = self.create_collection(dense_dim)
        return self.insert_reback(chunks, collection_name, file_title, milvus_client)






if __name__ == '__main__':
    node = NodeImportMilvus()
    with open(r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\embedding_chunk.json","r",encoding="utf-8") as f:
        chunks = json.load(f)
    init_state = {
        "chunks":chunks
    }
    result = node(init_state)
    logger.info(json_format_tool(result))