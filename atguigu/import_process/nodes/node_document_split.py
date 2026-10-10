# atguigu/import_process/nodes/node_document_split.py
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeDocumentSplit(NodeBase):
    """
    文档切分节点：智能文档切片
    整体执行流程：
    1. get_md_content：读取Markdown源文件，校验文件合法性，返回文件正文、文档标题、文件路径对象
    2. get_section_list：基于Markdown标题(# 一级~六级标题)做粗粒度分段，跳过代码块内部标题误判，生成标题+段落大章节
    3. get_final_section_list：对大章节做精细化递归文本切分，短文本直接保留，含表格章节禁止切分，长文本切片并增加段落序号part，落地chunks.json备份文件
    4. process：串联上述三个核心方法，将切片结果chunks写入图状态返回，供给后续向量入库节点使用
    """

    name = "node_document_split"

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

    def get_section_list(self, md_content, file_title):
        """
        Markdown粗分段：以#标题为分割线拆分大章节，规避代码块内#被识别为标题的BUG
        逻辑说明：
        1. 统一换行符为\n，兼容Windows(\r\n)、Mac(\r)换行格式
        2. 逐行遍历MD文本，通过正则识别```/~~~代码块围栏，标记代码块区间
        3. 仅在非代码块区域识别1~6级Markdown标题，遇到标题就截取上一个标题到当前行作为一个章节
        4. 循环结束后补充最后一段无尾部标题的剩余内容
        :param md_content: MD完整文本
        :param file_title: 文档总标题
        :return: section_list 粗分段章节列表，每个元素结构：{"title":章节标题,"content":章节完整内容,"file_title":文档总标题}
        """
        # 统一换行符，消除不同系统换行符差异
        md_content = md_content.replace('\r\n', '\n').replace('\r', '\n')
        # 按换行拆分为单行列表，用于逐行遍历判断标题与代码块
        md_line_list = md_content.split('\n')

        # 代码块围栏正则：匹配开头为3个及以上` 或 3个及以上~
        code_pattern = r"^(`{3,}|~{3,})"
        is_in_block = False  # 标记当前行是否处于代码块内部
        marker = None  # 记录当前代码块起始符号(` or ~~~)，用于精准闭合代码块

        # Markdown标题正则：匹配行首空格 + 1~6个# + 空格 + 标题正文
        title_pattern = r'^\s*#{1,6}\s+.+'
        current_index = 0  # 粗分段截取起始行下标
        section_list = []  # 存储粗分段结果

        for idx, line in enumerate(md_line_list):
            # 去除行首尾空白字符，减少无效空格干扰正则匹配
            line = line.strip()
            # 命中代码块围栏标记
            match = re.match(code_pattern, line)
            if match:
                if not is_in_block:
                    # 开启代码块，记录围栏符号
                    is_in_block = True
                    marker = match.group(1)   #group（1）是捕获分组，提取正则中第一个圆括号（）捕获到的内容
                    print(marker)
                    logger.info(f"开始代码块:{marker}")
                else:
                    # 匹配到相同围栏符号，闭合代码块
                    if marker == match.group(1):
                        is_in_block = False
                        marker = None
                        logger.info("结束代码块")

            # 仅在非代码块区域识别标题，避免代码注释#被误判为章节标题
            if not is_in_block and re.match(title_pattern, line):
                # 截取上一个分段起点到当前标题行，作为上一个章节完整内容
                temp_list = md_line_list[current_index:idx]
                content = '\n'.join(temp_list)
                # 组装章节结构，以章节首行作为标题，无#前缀则标记无标题
                section_dict = {
                    "title": temp_list[0] if content.startswith("#") else "无标题",
                    "content": content,
                    "file_title": file_title,
                }
                section_list.append(section_dict)
                # 更新分段起始下标为当前标题行，下一个章节从此行开始截取
                current_index = idx

        # 补充循环遗漏的最后一段内容（文档末尾没有收尾标题，直接截取剩余全部行）
        section_list.append(
            {
                "title": md_line_list[current_index],
                "content": "\n".join(md_line_list[current_index:]),
                "file_title": file_title
            })
        return section_list

    def get_final_section_list(self, file_title, section_list, md_path_obj):
        """
        精细化文本切片：对粗分章节做递归字符切割，适配向量库入库长度要求
        切片规则：
        1. 配置分片最大长度300，上下文重叠30字符（解决段落割裂语义丢失）
        2. 章节正文长度小于阈值：直接保留完整章节，part=0标识未拆分
        3. 章节包含HTML表格：禁止拆分，防止表格结构断裂失效，part=0
        4. 超长普通文本：剔除章节标题后对正文递归切分，每个分片拼接原章节标题，part标记分片序号
        5. 全部分片完成后，在MD同级目录生成chunks.json备份切片数据
        :param file_title: 文档总标题
        :param section_list: 粗分段章节数组
        :param md_path_obj: MD文件Path对象，用于输出chunks.json路径
        :return: final_section_list 最终可用于向量化的细粒度切片数组
        """
        # 切片基础配置
        max_length = 300  # 单块最大字符长度
        over_lap = 30  # 分片重叠字符数，保证上下文连贯性
        final_section_list = []

        # 递归字符分割器：按优先级分隔符拆分（换行段>换行>中文句号>中英文标点>空格）
        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_length,
            chunk_overlap=over_lap,
            # length_function= len()
        )

        # 遍历每一个粗分段章节，执行精细化切片逻辑
        for section in section_list:
            title = section.get("title")
            content = section.get("content")
            # 剥离章节标题，仅对正文内容做切片，切片后重新拼接标题保证语义完整
            real_content = content[len(title):] if content.startswith('#') else content

            # 场景1：正文长度较短，无需拆分直接入库
            if len(real_content) < max_length:
                final_section_list.append({
                    **section,
                    "part": 0  # part=0代表本章节未做二次拆分
                })
                continue
            # 场景2：章节内含表格标签，表格结构不可拆分，直接完整保留
            if "<table>" in real_content:
                final_section_list.append({
                    **section,
                    "part": 0
                })
                continue
            # 场景3：超长纯文本，执行递归切片
            splite_chunk_list = spliter.split_text(real_content)
            for idx, splite_chunk in enumerate(splite_chunk_list):
                final_section_list.append({
                    "title": title,
                    "file_title": file_title,  # 字段拼写为原始写法，不做修改
                    "content": title + "\n\n" + splite_chunk,  # 分片内容前置章节标题
                    "part": idx  # 分片序号，用于溯源分片属于原章节第几段
                })
        logger.info(json_format_tool(final_section_list))

        # 将所有细粒度切片持久化为JSON文件，用于调试、备份
        # with open(md_path_obj.parent / f"chunks.json", 'w', encoding='utf-8') as f:
        #     f.write(json_format_tool(final_section_list))
        return final_section_list

    def process(self, state: ImportGraphState):
        """
        LangGraph节点主执行入口，串联全流程
        完整链路：文件读取校验 -> MD标题粗分段 -> 精细化文本切片 -> 返回切片结果给图状态
        :param state: 上游传入的图状态字典，包含md_path、file_title
        :return: 字典{"chunks": 细粒度切片数组}，向下游向量嵌入、向量入库节点传递数据
        """
        # 步骤1：加载MD文件，校验文件合法性
        md_content, file_title, md_path_obj = self.get_md_content(state)
        # 步骤2：基于Markdown标题做粗粒度章节划分，过滤代码块标题误识别
        section_list = self.get_section_list(md_content, file_title)
        # 步骤3：章节精细化分片，长文本切割、表格保护、短文本直通，落地JSON备份
        final_section_list = self.get_final_section_list(file_title, section_list, md_path_obj)
        # 步骤4：将旅游元数据（内容类型/城市/文档名/主题/来源链接）附加到每个切片
        metadata = {
            "content_type": state.get("content_type", ""),
            "region": state.get("region", ""),
            "doc_name": state.get("doc_name", ""),
            "topics": state.get("topics", ""),
            "source_url": state.get("source_url", ""),
        }
        for chunk in final_section_list:
            chunk.update(metadata)
        # 将切片结果写入graph状态返回
        return {
            "chunks": final_section_list
        }

    # 原代码冗余return state直接注释保留，不删除原始代码
    # return state


if __name__ == '__main__':
    # 单元测试入口：实例化文档切片节点，传入本地MD路径测试完整切片流程
    node = NodeDocumentSplit()
    init_state = {
        "md_path": r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册_new.md",
        "file_title": 'hak180产品安全手册'
    }
    result = node(init_state)
    logger.info(json_format_tool(result))