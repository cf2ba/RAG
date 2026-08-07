# atguigu/import_process/nodes/node_item_name_recognition.py
import json

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    """

    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState):
        chunks = state.get("chunks",'')
        file_title = state.get("file_title")
        if not chunks:
            logger.error("chunks为空必须有值才能进行主体识别")
            raise Exception("chunk是空的，必须有值才能进行主题识别")
        if not file_title:
            logger.error("file_title是空的")
            raise Exception("file_title是空的")
        #根据chunks让大模型去识别主题名称（商品名字）
        #chunks有点多，内容加起来可能超过大模型的token限制，所以我们从chunks中截取几个
        chunk_k_list = chunks[:10]
        #需要把这些chunk的title,content,file_title  part把这些需要的数据拼接成字符串，还得把这些字符串拼接到一个大的字符串
        max_len = 1000
        content_str = '\n'
        for idx,chunk in enumerate(chunk_k_list,start=1):
            title = chunk.get("title")
            content = chunk.get("content")
            chunk_str = f"[切片{idx}]\n{file_title}\n{title}\n{content}"
            #判断content_str是不是已经超过max_len
            # content_str += chunk_str
            if len(content_str) > max_len:
                logger.info(f"已经超过最大长度，不再拼接")
                break
        content_str = content_str[:max_len]


        return state
if __name__ == '__main__':
    node = NodeItemNameRecognition()
    with open(r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\chunks.json",encoding="utf-8")as f:
        chunks =json.load(f)
    init_state={
        "chunks": chunks,
        "file_tile": "hak180产品安全手册_new",
    }
    result = node(init_state)
    logger.info(json_format_tool(result))