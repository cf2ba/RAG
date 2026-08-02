from langgraph.constants import START, END
from langgraph.graph import StateGraph

from atguigu.import_process.nodes.node_bge_embedding import NodeBGEEmbedding
from atguigu.import_process.nodes.node_document_split import NodeDocumentSplit
from atguigu.import_process.nodes.node_entry import NodeEntry
from atguigu.import_process.nodes.node_import_milvus import NodeImportMilvus
from atguigu.import_process.nodes.node_item_name_recognition import NodeItemNameRecognition
from atguigu.import_process.nodes.node_md_img import NodeMDImg
from atguigu.import_process.nodes.node_pdf_to_md import NodePDFToMD
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class  MainGraphRun:
    def __init__(self):
        self.builder = StateGraph(state_schema =ImportGraphState )
        self.add_node()
        self.add_edge()
        self.graph = None #单例对象保证一个类全局有且仅有一个实例对象，提供一个全局访问点获取该对象
    def add_node(self):
        self.builder.add_node(NodeEntry.name,NodeEntry())
        self.builder.add_node(NodePDFToMD.name,NodePDFToMD())
        self.builder.add_node(NodeMDImg.name,NodeMDImg())
        self.builder.add_node(NodeDocumentSplit.name,NodeDocumentSplit())
        self.builder.add_node(NodeItemNameRecognition.name,NodeItemNameRecognition())
        self.builder.add_node(NodeBGEEmbedding.name,NodeBGEEmbedding())
        self.builder.add_node(NodeImportMilvus.name,NodeImportMilvus())
    def after_condition_router(self,state:ImportGraphState):
        is_md_read_enabled = state.get('is_md_read_enabled',False)
        is_pdf_read_enabled = state.get('is_pdf_read_enabled',False)
        if is_md_read_enabled:
            return NodeMDImg.name
        elif is_pdf_read_enabled:
            return NodePDFToMD.name
        else:
            return END

    def add_edge(self):
        # self.builder.add_edge(START,NodeEntry.name)
        self.builder.set_entry_point(NodeEntry.name)
        self.builder.add_conditional_edges(NodeEntry.name,self.after_condition_router)
        self.builder.add_edge(NodePDFToMD.name,NodeMDImg.name)
        self.builder.add_edge(NodeMDImg.name, NodeDocumentSplit.name)
        self.builder.add_edge(NodeDocumentSplit.name, NodeItemNameRecognition.name)#NodeItemNameRecognition主题识别节点
        self.builder.add_edge(NodeItemNameRecognition.name, NodeBGEEmbedding.name)
        self.builder.add_edge(NodeBGEEmbedding.name, NodeImportMilvus.name)
        self.builder.add_edge(NodeImportMilvus.name, END)
    def run(self,state):
        if not self.graph:
            self.graph = self.builder.compile()
            return self.graph.invoke(state)

    @classmethod
    def creative_run(cls,state):
        return cls().run(state)
if __name__ == '__main__':
    init_state = {'local_file_path': r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册.pdf"}
    result = MainGraphRun.creative_run(init_state)
    logger.info(json_format_tool(result))



