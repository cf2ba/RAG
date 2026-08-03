import base64
import os
import re
import time
from collections import deque
from pathlib import Path

from langchain.chat_models import init_chat_model
from openai import base_url

from atguigu.config.config import LLMConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodeMdImage(NodeBase):
    name = 'node_md_image'
    def check_path(self,state:ImportGraphState):
        # 路径和文件判断
        md_path = state.get("md_path",'')
        if not md_path:
            logger.error("文件路径必须提供")
            raise ValueError("文件路径必须提供")

        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("文件不存在")
            raise ValueError("文件不存在")
        with open(md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()

        if not md_content:
            logger.error("文件内容不存在")
            raise ValueError("文件内容不存在")
        return  md_path_obj,md_content

    def get_image_with_context_list(self,image_name_list,image_name_path_dir_obj,md_content):
        # 去遍历看图片是否是符合markdown的格式
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        MAX_CONTEX_LENGTH = 200
        image_with_context_list = []
        for image_name in image_name_list:
            # 注意suffix是pathlib.Path 对象才有的
            if Path(image_name).suffix.lower() not in IMAGE_EXTENSIONS:
                logger.warning(f"图片{image_name}不符合markdown格式")
                continue
            # 如果符合格式则去正则，判断每张图片是否在markdown中应用
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_name) + r"\)")
            # 拿到了图片的起始位置可以根据起始位置去找上下文
            match = pattern.search(md_content)
            #print(match
            if not match:
                logger.warning(f"图片{image_name}未被引用")
                continue
            start, end = match.span()
            pre_text = md_content[max(0, start - MAX_CONTEX_LENGTH):start]
            post_text = md_content[end:min(len(md_content), end + MAX_CONTEX_LENGTH)]
            # 将我们的图片上下文还有图片和图片路径放在一个字典列表中
            image_path = str(image_name_path_dir_obj / image_name)
            image_with_context_list.append({
                "image_name": image_name,
                "pre_text": pre_text,
                "post_text": post_text,
                "image_path": image_path
            })
        return image_with_context_list
    def get_image_with_summary_list(self,image_with_context_list):
        # 实例化大模型对象
        llm = init_chat_model(
            # 视觉模型
            model=LLMConfig.vl_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base_url,
            temperature=LLMConfig.llm_default_temperature
        )
        # print(json_format_tool(image_with_context_list))
        # 根据上边的图片列表，进行大模型调用生成真正的图片摘要
        dq = deque(maxlen=30)  # maxlen令牌桶的最大长度
        current_time = time.time()
        image_with_summary_list = []
        for image_with_context in image_with_context_list:
            # 调用大模型生成摘要
            # 令牌桶实现模型限流
            # 进入循环，先盲清一波过期的请求，如果队列中有超过一分钟的请求则清出令牌桶
            while dq and current_time - dq[0] > 60:
                dq.popleft()
            # 有两种情况 如果队列中所有令牌都没达到1分钟没有过期没有被清理的/队列中有过期的被清理的
            # 判断队列位置是否满了，如果满了就需要等待，如果没满就发送请求，把十几家加入
            # 如果dq存在且令牌桶满，需要等待
            if dq and len(dq) == dq.maxlen:
                need_wait_time = 60 - (current_time - dq[0])
                if need_wait_time > 0:
                    time.sleep(need_wait_time)  # 真正的等待
                    current_time = time.time()
                    while dq and current_time - dq[0] > 60:
                        dq.popleft()
            # 因为清理完过期记录后，当前请求已经“通过”了限流检查，
            # 需要把自己的时间戳记录到队列中，
            # 作为窗口内的最新一笔记录。
            # 这样后续的请求才能基于这个新记录继续判断是否超限。
            # 如果不 append，队列长度会减少，限流状态就无法持续追踪，
            # 后续请求会错误地认为窗口未满而放行，导致限流失效。
            dq.append(current_time)
            # 使用base64 优势减少http请求数
            with open(image_with_context.get("image_path"), "rb") as f:
                image_data = f.read()
                base64_str = base64.b64encode(image_data).decode("utf-8")
            # 给大模型发请求
                # 构造提示词：参考阿里云百炼提供的提示词
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64,"+ base64_str,
                            },
                        },
                        {"type": "text",
                         "text": f"这是一张图片，图片的上文部分为{image_with_context.get("pre_text")},图片的下文为{image_with_context.get("post_text")},请用中文摘要总结这张图片的摘要，字数在50字以内"},
                    ],
                },
            ]
            result = llm.invoke(input=messages)

            image_with_summary_list.append({
                "image_name": image_with_context.get("image_name"),
                "image_path": image_with_context.get("image_path"),
                "summary": result.content
            })
        return json_format_tool(image_with_summary_list)

    def process(self,state:ImportGraphState):
        #第一大步获取md的路径对象和内容和文件判断
        md_path_obj, md_content = self.check_path(state)
        #判断图片存储路径是否存在，如果不存在则直接返回md_content不对图片处理
        image_name_path_dir_obj = md_path_obj.parent / "images"
        if not image_name_path_dir_obj.exists():
            return {
                "md_content":md_content
            }
       #判断图片目录中有没有内容
        image_name_list = os.listdir(image_name_path_dir_obj)
        if not image_name_list:
            logger.info("图片目录为空")
            return {
                "md_content":md_content
            }


        #走到这意味着存储图片的目录存在，接下来去拿到图片名字列表
        #第二大部：获取图片的上下问列表，根据图片正则拿到图片位置，获取上下文
        image_with_context_list = self.get_image_with_context_list(image_name_list,image_name_path_dir_obj,md_content)
        #第三大步:更具第二步得到的上下文图片列表，进行大模型调用真正生成摘要，形成新的图片字典列表
        image_with_summary_list = self.get_image_with_summary_list(image_with_context_list)
        return image_with_summary_list
if __name__ == '__main__':
    node = NodeMdImage()
    init_state = {
        "md_path":r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册.md"
    }
    result = node(init_state)
    print(result)