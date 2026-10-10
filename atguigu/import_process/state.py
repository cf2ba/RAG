# atguigu/import_process/state.py

from typing import TypedDict

class ImportGraphState(TypedDict):
    """
    图的状态定义，包含所有节点产生和消费的数据字段
    """
    task_id: str # 任务唯一ID，用于追踪日志

    #流程控制标记
    is_md_read_enabled: bool    # 是否启用 Markdown 读取路径
    is_pdf_read_enabled: bool   # 是否启用 PDF 读取路径

    # 路径相关
    local_dir: str  # 当前工作目录或输出目录
    local_file_path: str    # 原始输入文件路径
    file_title: str # 文件标题（文件名去后缀）
    pdf_path: str   # PDF 文件路径 (如果输入是PDF)
    md_path: str    # Markdown 文件路径 (转换后或直接输入的)

    # 内容数据
    md_content: str # Markdown 的全文内容
    chunks: list    # 切片列表
    item_name:str # 识别主体的名称（例如：万用表）

    # 元数据（旅游知识库，导入时随文件一并传入，最终落到每个切片）
    content_type: str   # 内容类型：景点介绍/线路推荐/酒店信息/美食推荐/交通指南/文化民俗
    region: str         # 地区/城市/目的地
    doc_name: str       # 文档/线路/景点/酒店名称
    topics: str         # 主题关键词（逗号分隔）
    source_url: str     # 来源路径或资源链接

    # 数据库关联
    embeddings_content: list # 包含向量数的列表 ，准备写入 Milvus