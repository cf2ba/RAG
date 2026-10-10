# atguigu/import_process/nodes/node_entry.py
from pathlib import Path

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeEntry(NodeBase):
    """
    入口节点：任务分发
    """
    name = "node_entry"

    def process(self, state: ImportGraphState):
        #编程防御性
        local_file_path = state.get('local_file_path','')
        if not local_file_path:
            logger.error("入口节点必须传入路径")
            raise ValueError("入口节点必须传入路径")
        local_file_path_obj= Path(local_file_path)
        if not local_file_path_obj.exists():
            logger.error("入口节点必须传入文件路径")
            raise ValueError("入口节点必须传入文件路径")
        #文件前缀
        file_title = local_file_path_obj.stem
        # print(file_title)
        #文件后缀
        suffix = local_file_path_obj.suffix
        # print(suffix)
        #判断文件的后缀返回修改的state增量数据
			# 如果是.pdf pdf_path=local_file_path  设置is_pdf_read_enabled=True  设置文件名
			# 如果是.md  md_path=local_file_path   设置is_md_read_enabled=True   设置文件名
			# 如果是其他，抛异常
        if suffix.lower() == '.md':
            return {
                "file_title":file_title,
                "md_path":str(local_file_path_obj),
                "is_md_read_enabled":True,
            }
        elif suffix.lower() == '.pdf':
            return{
                "file_title":file_title,
                "pdf_path":str(local_file_path_obj),
                "is_pdf_read_enabled":True,
            }
        else:
            logger.info('暂只接收pdf和md文件不能处理其他文件')
            raise Exception('暂只接收pdf和md文件不能处理其他文件')


        return state
if __name__ == '__main__':
    #给一个文件路径
    state = {'local_file_path':r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册.pdf"}
    node = NodeEntry()
    result = node(state)
    logger.info(json_format_tool(result))