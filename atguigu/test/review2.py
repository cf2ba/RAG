#再盘一遍文件切分节点
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from atguigu.import_process.base import NodeBase
from atguigu.test.node_md_image import current_time
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeDocumentSplite(NodeBase):
    name = "node_document_splite"

    def get_md_content(self, state):
        """
        读取MD文件基础信息并做前置合法性校验
        :param state: LangGraph流转状态字典，存储md_path、file_title参数
        :return: md_content:MD全文文本, file_title:文档标题, md_path_obj:Path格式文件路径对象
        :raises ValueError: 未传入md_path参数
        :raises Exception: 文件为空、文件路径不存在
        """
        # 从流转状态获取MD文件路径
        md_path = state.get("md_path", '')
        if not md_path:
            logger.error("md_path必须提供")
            raise ValueError("md_path必须提供")
        # 转为Path对象方便文件操作
        md_path_obj = Path(md_path)
        # 校验文件物理存在
        if not md_path_obj.exists():
            logger.error("文件不存在")
            raise ValueError("文件不存在")

        # 读取文档标题，无自定义标题则使用文件名作为标题
        file_title = state.get("file_title", '')
        if not file_title:
            file_title = md_path_obj.stem
        # 以UTF-8编码读取完整MD文件内容
        with open(md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()
        # 校验文件非空
        if not md_content:
            logger.error(f"文件内容为空:{md_path}")
            raise Exception("文件内容为空")
        return md_content, file_title, md_path_obj
    #实现粗切分
    def get_section_list(self,md_content,file_title):
        #先转义换行符
        md_content = md_content.replace("\r\n","\n").replace("\r","\n")
        #按行划分
        md_line_list = md_content.split("\n")
        #粗分按照一个标题进行一个章节一个章节的划分  #按标题划分那就要考虑#是在哪了，如果在代码块围栏那就是注释
        #先根据正则去看代码框围栏
        code_pattern = []
        is_code_index = False
        marker = None #用来标识代码块是以```还是~~~开始
        section_list = []
        current_time = 0
        title_pattern = r'^\s*#{1,6}\s+.+'
        for idx,md_line in enumerate(md_line_list):
            md_line = md_line.strip()
            match = re.compile(code_pattern,md_line) #这是代码块，如果在代码块，那我们就要考虑它是代码块的开始还是结束，所以就需要一个占位符
            if match:
                if not is_code_index:
                    is_code_index = True
                    marker = match.group(1)
                    logger.info("代码框的开始")
                else:
                    if marker == match.group(1):
                        is_code_index =False
                        marker = None
                        logger.info("代码块的结束")
            #不在代码框那就是判断是不是标题
            if not is_code_index and re.match(title_pattern,md_line):
                temp_list = md_line_list[current_time,idx]
                content = "\n".join(temp_list)
                section_list.append({
                    "title":temp_list[0] if content.startwith("#") else  "没有标题",
                    "content":content,
                    "file_title":file_title
                })
            #更新当前current_time = idx
            current_time = idx
            #还要考虑到最后一章节其下边没有标题
            section_list.append({
                "title":md_line_list[current_time],
                "content":md_line_list[current_time:],
                "file_title":file_title
            })

        return section_list

    def get_final_section_list(self,section_list,file_title,md_path_obj):
        max_len = 300
        over_lap = 30
        final_section_list = []
        #用真实的内容去切
        #构造
        splite =RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_len,
            chunk_overlap=over_lap
        )
        for section in section_list:
            content = section_list.get("content")
            title = section_list.get("title")
            #content -title
            real_content = content[len(title):] if content.startwith("#") else content
        #考虑到如果章节长度不足chunk_size不用切片
            if len(real_content) < max_len:
                final_section_list.append(
                    { **section,
                    "part":0}
                )
                continue
            if "<table>" in real_content:
                final_section_list.appen(
                    {
                        **section,
                        "part":0
                    }

                )
                continue
            splite_list = splite.split_text(real_content)
            for chunk in splite_list:
                final_section_list.append({
                    "title":title,
                    "file_title":file_title,
                    "content":title +"\n\n"+ chunk
                })
        with open(md_path_obj.parent/f"chunks1.json","w",encoding="utf-8") as f:
            f.write(json_format_tool(final_section_list))

        return final_section_list







    def processs(self,state):
        pass

if __name__ == '__main__':
    node = NodeDocumentSplite()
    init_state = {
        "md_path":r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册_new.md",
    }

    result = node(init_state)
    logger.info(json_format_tool(result))