#图片处理节点
import base64
import os
import re
import time
from collections import deque
from pathlib import Path

from ada92cb5d92a588d1b93__mypyc import init_charset_normalizer___md
from langchain.chat_models import init_chat_model
from minio.deleteobjects import DeleteObject
from pymongo.common import MAX_CONNECTING

from atguigu.config.config import LLMConfig, MineruToken, MinIoConfig
from atguigu.import_process.base import NodeBase
from atguigu.test.node_md_image import need_wait_time
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client


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
            pattern = re.match(r"!\[.*?\]\(.*?" + re.escape(image_name) + r"\)")
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

    def get_image_with_summary_list(self,image_with_context_list):
        #初始化大模型
        llm = init_chat_model(
            model = LLMConfig.vl_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base_url,
            temperature = float(LLMConfig.llm_default_temperature)
        )
        # MAX_CONTEXT_LEN = 200
        dq = deque(max_len = 30)

        for image_with_context in image_with_context_list:
            current_time = time.time()
            #上来先盲清一波
            while dq and current_time - dq[0] > 60:
                dq.popleft()
                current_time = time.time()

            if dq and len(dq) == dq.maxlen:
                current_time = time.time()
                #需要等待
                need_wait_time = 60 - (current_time - dq[0])
                if need_wait_time >0:
                    time.sleep(need_wait_time)
                current_time = time.time()
                while dq and current_time-dq[0] >60:
                    dq.popleft()

            # 因为大模型有限流所以用滑动窗口算法
            dq.append(current_time)
            #接下来就是对图片处理为base64，减少http请求#让 数据再文本协议安全传输
            with open(image_with_context.get("image_path"),'rb') as f:
                image_data = f.read()
                base64_str = base64.b64encode(image_data).decode("utf-8")
            #给大模型的发送请求
            #构造提示词参考阿里云
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64," + base64_str,
                            },
                        },
                        {
                            "type": "text",
                            "text": f"这是一张图片，图片的上文部分为{image_with_context.get('pre_text')},图片的下文为{image_with_context.get('post_text')},请用中文摘要总结这张图片的摘要，字数在50字以内"
                        },
                    ],
                },
            ]
            result = llm.invoke(messages)

            image_with_context_list.append(
                {
                    "image_name":image_with_context.get("image_name"),
                    "image_path":image_with_context.get("image_path"),
                    "summary":result.content
                }
            )
            return image_with_context_list

        #获取图片url通过minio中间工具实现
        def get_image_with_summary_and_url_list(self,image_with_summary_list):
            minio_client = get_minio_client()
            upload_dir = MinIoConfig.minio_img_dir
            #考虑到可能有历史图片在上传路径下，所以需要做一个幂等性删除
            old_image_list = minio_client.list_objects(bucket_name=MinIoConfig.minio_bucket_name,prefix= upload_dir,recursive= True)
            #幂等性删除但参数需要的必须是DeleteObject对象
            delete_image_list = [DeleteObject(obj.object_name) for obj in old_image_list]
            errors = minio_client.remove_object(bucket_name=MinIoConfig.minio_bucket_name,delete_object_list = delete_image_list)
            #删除后上传图片到minio
            image_with_summary_url_list  = []
            for image_with_summary in image_with_summary_list :
                minio_client.fget_object(

                )










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