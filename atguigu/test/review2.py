# 这是分片节点
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.test.node_md_image import current_time
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NondeDocumentSplit(NodeBase):
    name = "node_document_split"

    # 防御性判断
    def get_md_content(self, state):
        md_path = state.get("md_path", '')
        if not md_path:
            logger.error("md_path必须提供")
            raise Exception("md_path必须提供")
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("文件不存在")
            raise Exception("文件不存在")
        with open(md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()
        if not md_content:
            logger.error("没有内容")
            raise Exception("文件没内容")
        file_title = state.get("file_title", '')
        if not file_title:
            file_title = md_path_obj.stem
        return md_path_obj, md_content, file_title

    # 粗分按照标题去划分将整个文本文件按照标题划分为一个个的大章节
    def get_section_list(self, md_content, file_title):
        # 先将整个文本按行去划分
        # 由于不同的系统所用到的换行符不同，所以先进行换行符的转义
        md_content = md_content.replace("\r\n", '\n').replace("\r", "\n")
        md_line_list = md_content.split("\n")
        # 判断是不是一个标题呢通过#来判断，但是在代码块代码围栏中#是注释，所以我们先要判断是不是在代码围栏中，怎么判断他是不是一个代码围栏呢，就要判断他是不是以~~~或这```开头
        # 正则判断是不是代码围栏
        code_pattern = r"^(`{3,}|~{3,})"
        # 如果是代码围栏，那我们就要考虑代码块是否结束，下一个#是不是注释
        # 还有有一个占位去判断是不是同一个代码围栏，因为可能会出现多个代码围栏嵌套的存在不知道
        marker = None
        is_code_block = False
        current_index = 0
        section_list = []
        title_pattern = r'^\s*#{1,6}\s+.+'  # 标题索引
        for idx, md_line in enumerate(md_line_list):
            code_match = re.match(code_pattern, md_line)
            if code_match:
                is_code_block = True
                marker = code_match.group(1)
                logger.info("是代码围栏开头")
            else:
                is_code_block = False
                marker = None
                logger.info("是代码围栏结束")
            # 如果走到这那就是不是代码围栏，那我们就进行拼接，需要是标题且不是代码围栏且满足标题索引
            if not code_match and re.match(title_pattern, md_line):
                temp = md_line_list[current_index:idx]
                content = "\n".join(temp)
                section_list.append({
                    "title": temp[0] if content.startswith("#") else "无标题",
                    "file_title": file_title,
                    "content": content

                })
            # 更新当前的index
            current_index = idx
            # 最后一个大的章节后边没有标题
        section_list.append(
            {
                "title": md_line_list[current_index],
                "file_title": file_title,
                "content": "\n".join(md_line_list[current_index:])
            }
        )
        return section_list  # 上边实现了粗分

    # 下边细分长分短合
    def get_final_section_list(self, section_list, file_title):
        # 定义一个章节的最大长度
        max_len = 300
        over_lap = 30
        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_len,
            chunk_overlap=over_lap,
        )
        final_section_list = []

        for section in section_list:
            content = section.get("content")  # 内容
            title = section.get("title")
            # 就要考虑标题在内容中的影响，如果一个章节进行切分为多个部分,那除了切出来的第一部分有标题信息，其他部分没有标题信息，
            # 后边检索的时候可能会把他判断到其他标题下去，同时也是为了未来方便溯源，后边有用户反馈RAG有一标题下的知识有问题时可以通过标题很快找到有问题的地方
            # 所以我们就拿真正的内容去切分，不用拿标题
            # 真实的内容时content - title  要考虑有没有标题的情况 如果没有标题  通过切片实现
            real_content = content[len(title):] if content.startswith('#') else content
            # 拿到真实的内容去切片用递归分割器 需要进行判断，如果章节比我们要切分的chunk_size小那就不去切分
            if len(real_content) < max_len:
                final_section_list.append({
                    **section,
                    "part": 0  # 去标识是否切分
                })
            # 考虑如果章节是表格，也不进行切分否则可能会破坏表格
            # if real_content.startwith("<table>"):
            if "<table" in real_content:
                final_section_list.append({
                    **section,
                    "part": 0  # 去标识是否切分
                })
            # 走到这说明不是以上两种情况可以直接去切分了
            split_chunk_list = spliter.split_text(real_content)
            # print(split_list)
            for idx, chunk in enumerate(split_chunk_list):
                final_section_list.append({
                    "title": title,
                    "file_title": file_title,
                    "count": title + "\n\n" + chunk,
                    "part": idx

                })
        return final_section_list

        # 转移后按照章节标题前的内容进行拼接作为上一个标题下的内容
        # if

    def process(self, state: ImportGraphState):
        md_path_obj, md_content, file_title = self.get_md_content(state)
        section_list = self.get_section_list(md_content, file_title)
        final_section_list = self.get_final_section_list(section_list, file_title)

        # 将final_section_list 保存到文件中
        with open(md_path_obj.parent/ f"split_chunk.json", "w", encoding="utf-8") as f:
            f.write(json_format_tool(final_section_list))

        return {
            "final_section_list": final_section_list
        }

        pass


if __name__ == '__main__':
    node = NondeDocumentSplit()
    init_state = {
        "md_path": r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册_new.md"

    }
    result = node(init_state)
    logger.info(json_format_tool(result))
