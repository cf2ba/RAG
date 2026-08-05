#图片处理节点
import os
import re
from pathlib import Path

from atguigu.import_process.base import NodeBase
from atguigu.tool.logger import logger


class NodeMdImg(NodeBase):
    name = 'nodemdimg'

    def check_path(self, state):
        md_path = state.get("md_path", '')
        if not md_path:
            logger.error("md_path必须提供")
            raise ValueError("md_path必须提供")
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("文件不存在")
            raise ValueError("文件不存在")

        file_title = state.get("file_title", '')
        if not file_title:
            file_title = md_path_obj.stem
        with open(md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()
        if not md_content:
            logger.error(f"文件内容为空:{md_path}")
            raise Exception("文件内容为空")
        return md_path_obj, md_content


    def get_image_with_context_list(self,image_name_list,md_content,image_name_path_dir_obj):
        # 看图片是否符合markdown格式
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        MAX_CONTEXT_LEN = 200
        image_with_context_list = []
        for image_name in image_name_list:
            if image_name not in IMAGE_EXTENSIONS:
                logger.error("图片不符合markdown的格式")
                continue
            # 正则化去看判断图片是否属于markdown
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_name) + r"\)")
            # 拿到图片的起始和结束位置
            match = pattern.search(md_content)
            # 判断match是否有没有则图片没在markdown中使用
            if not match:
                logger.info("图片未被markdown引用")
                continue
            start, end = match.span()
            pre_context = md_content[max(0, start - MAX_CONTEXT_LEN):start]
            post_context = md_content[end:min(len(md_content), end + MAX_CONTEXT_LEN)]
            image_path = str(image_name_path_dir_obj / image_name)
            image_with_context_list.append({
                "image_name": image_name,
                "pre_context": pre_context,
                "post_context": post_context,
                "image_path": image_path
            })

            return image_with_context_list



    def process(self,state):
        md_path_obj, md_content = self.check_path(state)
        # 判断图片存储路径是否存在，如果不存在则直接返回md_content不对图片处理
        image_name_path_dir_obj = md_path_obj.parent / "images"
        if not image_name_path_dir_obj.exists():
            return {
                "md_content": md_content
            }
        #将图片的内容和图片的上下文交给大模型让大模型生成图片摘要








        pass
if __name__ == '__main__':
    node = NodeMdImg()
    init_state = {
        "md_path":r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册.md"
    }