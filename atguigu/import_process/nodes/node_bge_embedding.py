# atguigu/import_process/nodes/node_bge_embedding.py
import json

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeBGEEmbedding(NodeBase):
    """
    混合向量化节点：使用 BGE-M3 模型将文本转换为向量
    """

    name = "node_bge_embedding"

    def process(self, state: ImportGraphState):
        chunks = state.get("chunks",'')
        if not chunks:
            logger.error("chunks不存在")
            raise Exception("chunks不能为空")
        logger.info(json_format_tool(chunks))

        #此处调用BGE模型进行向量化，做批处理 #每次处理3
        for i in range(0,len(chunks),3):
            chunk_k_list = chunks[i:i+3]
            chunk_k_content_list = [f"{chunk.get("item_name")}{chunk.get("content")}" for chunk in chunk_k_list]
            #向量化这一批三个内容列表
            embedding = get_bge_m3_embedding(chunk_k_content_list)
            #回填
            for idx,chunk in enumerate(chunk_k_list):
                chunk["dense_vector"]=embedding.get("dense")[idx]
                chunk["sparse_vector"] = embedding.get("sparse")[idx]
        logger.info(json_format_tool(chunks))
        #备份chunks，下个节点测试使用
        with open(r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\embedding_chunk.json","w",encoding="utf-8") as f:
            f.write(json_format_tool(chunks))



        return {
            "chunks":chunks
        }
if __name__ == '__main__':
    node = NodeBGEEmbedding()
    with open(r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\item_name_embedding.json","r",encoding= "utf-8") as f:
        chunks = json.load(f)
    init_state = {
        "chunks":chunks
    }
    result = node(init_state)
    logger.info(json_format_tool(result))