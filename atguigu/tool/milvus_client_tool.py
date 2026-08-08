from pymilvus import MilvusClient

from atguigu.config.config import MilvusConfig

milvus_client = None
#milvus_client客户端工具
def get_milvus_client():
    global milvus_client
    if not milvus_client:
        milvus_client = MilvusClient(
            uri =MilvusConfig.milvus_url
        )
    return milvus_client
