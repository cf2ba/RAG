import time

from pymilvus import MilvusClient, AnnSearchRequest, WeightedRanker

from atguigu.config.config import MilvusConfig
from atguigu.tool.logger import logger

milvus_client = None
#milvus_client客户端工具
def get_milvus_client():
    global milvus_client
    if not milvus_client:
        milvus_client = MilvusClient(
            uri =MilvusConfig.milvus_url
        )
    return milvus_client


def get_chunks_collection() -> str:
    """返回当前应使用的切片集合名：启用旅游集合则返回旅游集合，否则返回默认商品集合"""
    if MilvusConfig.use_travel_collection and MilvusConfig.travel_chunks_collection:
        return MilvusConfig.travel_chunks_collection
    return MilvusConfig.chunks_collection


def load_collection_safe(milvus_client: MilvusClient, collection_name: str, timeout: float = 60.0) -> None:
    """
    幂等加载集合，并等待真正加载完成。

    Milvus 的 load_collection 是异步的：调用后立即返回，但集合尚未真正加载到内存，
    若紧接着执行 delete/query/search 会报 (code=101, collection not loaded)。
    这里先幂等触发加载（已加载时二次 load 会抛 'collection already loaded'，忽略），
    再轮询 get_load_state 直到 Loaded 才返回。
    """
    # 1) 幂等触发加载
    try:
        milvus_client.load_collection(collection_name=collection_name)
    except Exception as e:
        if "already loaded" not in str(e).lower():
            raise

    # 2) 等待真正加载完成，否则后续 delete 会报 collection not loaded
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = milvus_client.get_load_state(collection_name=collection_name)
            if isinstance(state, dict):
                state = state.get("state")
            if "loaded" in str(state).lower():
                return
        except Exception:
            pass  # 查询加载状态失败，稍后重试
        time.sleep(0.5)
    logger.warning(f"集合 {collection_name} 加载等待超时({timeout}s)，后续操作可能仍报 collection not loaded")


def truncate_utf8(text: str, max_bytes: int) -> str:
    """
    按 UTF-8 字节数截断字符串。

    Milvus 的 VARCHAR max_length 按 UTF-8 字节计数（一个中文占 3 字节），
    而 Python 的 len()/切片按字符计数，直接用 [:max] 对中文无效
    （46 个中文 = 138 字节 > 100 上限）。
    """
    if not text:
        return ""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    # 截断到 max_bytes，并用 errors="ignore" 丢弃被切断的多字节字符尾部
    return data[:max_bytes].decode("utf-8", errors="ignore")


def get_item_name_collection() -> str:
    """返回当前应使用的主体名称集合名：启用旅游集合则返回旅游集合，否则返回默认商品集合"""
    if MilvusConfig.use_travel_collection and MilvusConfig.travel_item_name_collection:
        return MilvusConfig.travel_item_name_collection
    return MilvusConfig.item_name_collection



def create_reqs(
        dense_data,
        sparse_data,
        dense_anns_field=None,
        sparse_anns_field=None,
        limit=10,
        dense_param=None,
        sparse_param=None,
        expr=None
        ):
    if not dense_param:
        dense_param = {
            "metric_type":"COSINE"
        }
    if not sparse_param:
        sparse_param = {
            "metric_type":"IP"
        }
    dense_req = AnnSearchRequest(
        data=[dense_data],
        anns_field=dense_anns_field,
        limit=limit,
        param=dense_param,
        expr=expr
    )#稠
    sparse_req = AnnSearchRequest(
        data=[sparse_data],
        anns_field=sparse_anns_field,
        limit=limit,
        param=sparse_param,
        expr=expr
    )#稀疏
    return [dense_req,sparse_req]

def search_hybrid(collection_name,reqs,ranker=(0.5,0.5),limit=10,output_fields=None):
    milvus_client=get_milvus_client()
    #自己分配权重
    weight_ranker = WeightedRanker(ranker[0],ranker[1],norm_score=True)



    res = milvus_client.hybrid_search(
        collection_name=collection_name,
        reqs=reqs,
        ranker=weight_ranker,
        limit=limit,
        output_fields=output_fields
    )
    return res