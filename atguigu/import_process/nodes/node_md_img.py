# atguigu/import_process/nodes/node_md_img.py
import os
import re
from pathlib import Path

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeMDImg(NodeBase):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        #1.获取文件内容和本地图片名字列表
        md_path = state.get("md_path",'')
        if not md_path:
            logger.error("md_path必须提供")
            raise ValueError("md_path必须提供")
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("md_path文件不存在")
            raise FileNotFoundError("md_path文件不存在")
        #根据md_path获取文件的内容
        with open(md_path_obj,"r",encoding="utf-8") as f:
            md_content = f.read()
        if not md_content:
            logger.error('文件内容为空')
            raise ValueError("md文件内容为空")
        #构造图片存储路径

        imagers_dir_path_obj = md_path_obj.parent/'images'
        if not imagers_dir_path_obj.exists():
            return md_content
        #判断图片目录下是否为图片
        #os.listdir列出目录下的所有文件夹和文件夹的名字
        # 获取本地文件中图片名字列表
        image_name_list = os.listdir(imagers_dir_path_obj)
        print(image_name_list)
        if not image_name_list:
            logger.info("图片目录为空")
            return md_content
        #2.图片摘要（让大模型完成 #多模态理解模型） 需要图片上文/图片下文/图片
        #2.1遍历图片，获取图片的上下文以及图片放在字典列表中存储
        #markdown的标准
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        MAX_CONTEXT_LENGTH = 250
        image_with_contex_list = []
        for image_name in image_name_list:
        # 判断名字是否符合markdown的标准
            if Path(image_name).suffix.lower() not in IMAGE_EXTENSIONS:
                logger.warning(f"图片{image_name}不是支持的格式")
                continue
        # re.compile（）将正则表达式模式字符串编译成一个正则表达式对象（Pattern），之后可以用它的search()、match()、findall()等方法进行匹配。
            #构建图片在markdown当中的正则对象 看图片在markdown中是否使用
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_name) + r"\)")
            #从长串中找符合正则规则的内容，第一个开始找，找到了图片的span()图片的起始位置
            match = pattern.search(md_content)
            # print(match)
            if not match:
                logger.warning(f"图片{image_name}未被引用")
                continue

            #获取匹配到的图片的起始和结束位置
            start,end = match.span()
            #找图片的上下文 字符串切片
            #max(0,start-MAX_CONTEXT_LENGTH)考虑到没有上文
            #min(len(md_content),end+MAX_CONTEXT_LEGTH) 考虑到没有下文
            pre_text = md_content[max(0,start-MAX_CONTEXT_LENGTH):start]
            post_text = md_content[end:min(len(md_content),end+MAX_CONTEXT_LENGTH)]
            #把图片和图片的上下构造成成字典中存储到意见构造好的列表中
            #构造图片的路径一起放在字典
            image_path =str(imagers_dir_path_obj/image_name)
            image_with_contex_list.append(
                {
                    "image_name":image_name,
                    "pre_text":pre_text,
                    "post_text":post_text,
                    "image_path":image_path
                }
            )
        print(json_format_tool(image_with_contex_list))


        return state
if __name__ == '__main__':
    node = NodeMDImg()
    init_state = {
        "md_path":r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册.md"
    }
    result = node(init_state)
    logger.info(json_format_tool(result))