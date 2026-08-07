from typing import List

from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from atguigu.config.config import EmbeddingConfig
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger

bge_m3_model = None #单例
#模型
def get_bge_m3_model():
    global  bge_m3_model
    if not bge_m3_model:
        #比较灵活，稠密向量和稀疏向量需要自己整理封装
        bge_m3_model = BGEM3EmbeddingFunction(
            model_name= EmbeddingConfig.bge_m3_path ,
            device = EmbeddingConfig.bge_device,
            use_fp16= EmbeddingConfig.bge_fp16
        )
    return bge_m3_model


#做向量化
def get_bge_m3_embedding(texts: List[str]):
    bge_m3_model = get_bge_m3_model()
    embedding = bge_m3_model.encode_documents(texts)
    print(embedding.get("dense"))
    print(embedding.get("sparse"))   #前一列位置 后一列分数
    #打印查看稠密向量的本质类型
    # for dense_item  in embedding.get("dense"):
    #     print(dense_item,type(dense_item))
    # #
    # for sparse_item in embedding.get("sparse"):
    #     print(sparse_item.__dict__)#转为字典

    #打印去看，如果是一个对象就转为字典去查看
    # {'_shape': (250002,), 'maxprint': 50, 'indices': array([31, 33600]), 'indptr': array([0, 2]),
    #  'data': array([0.24338958, 0.2583831])}
    #稀疏矩阵indices地址     #data 稀疏矩阵的分数
    # return {
    #     "dense":[list([float(item)  for item in dense_item]) for dense_item in embedding.get("dense")],
    #     "sparse":[dict(zip([int(indice) for indice in sparse_item.indices],[float(data) for  data in  sparse_item.data])) for sparse_item in embedding.get("sparse")]
    # }

    return {
        "dense":[list( dense_item.tolist()) for dense_item in embedding.get("dense")],
        "sparse":[dict(zip( sparse_item.indices.tolist(),  sparse_item.data.tolist())) for sparse_item in embedding.get("sparse")]
    }



if __name__ == '__main__':
    texts = ["hello","world"]
    result = get_bge_m3_embedding(texts)
    logger.info(json_format_tool(result))
