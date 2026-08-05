import base64
import os
import re
import time
from collections import deque
from pathlib import Path

from langchain.chat_models import init_chat_model
from minio.deleteobjects import DeleteObject
from openai import base_url

from atguigu.config.config import LLMConfig, MinIoConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import  get_minio_client


class NodeMdImage(NodeBase):
    """
    Markdown图片处理节点
    功能：校验MD文件、匹配文档内引用图片、截取图片前后上下文、基于视觉大模型生成图片摘要
    """
    name = 'node_md_image'

    def check_path(self, state: ImportGraphState):
        """
        路径和文件合法性校验，读取MD原文内容
        :param state: 图状态结构体
        :return: md_path_obj(Path对象), md_content(文档全文字符串)
        """
        # 路径和文件判断
        md_path = state.get("md_path", '')
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

        return md_path_obj, md_content

    def get_image_with_context_list(self, image_name_list, image_name_path_dir_obj, md_content):
        """
        遍历图片目录，筛选有效图片，正则匹配MD内图片引用位置，截取图片前后上下文文本
        :param image_name_list: 图片文件夹下所有文件名列表
        :param image_name_path_dir_obj: 图片文件夹路径Path对象
        :param md_content: Markdown完整文本内容
        :return: 带上下文、路径、图片名的字典列表
        """
        # 支持的图片后缀格式集合
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        # 上下文截取最大字符长度
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
            # print(match)
            if not match:
                logger.warning(f"图片{image_name}未被引用")
                continue

            start, end = match.span()
            #图片上文
            pre_text = md_content[max(0, start - MAX_CONTEX_LENGTH):start]
            #图片下文
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

    def get_image_with_summary_list(self, image_with_context_list):
        """
        初始化视觉大模型 + 滑动时间窗口限流控制请求频次
        读取图片转base64，结合图片前后上下文调用VL模型生成图片摘要
        :param image_with_context_list: 携带上下文的图片信息列表
        :return: 经过json格式化工具处理后的图片摘要结果
        """
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
        dq = deque(maxlen=30)  # 滑动窗口：60秒内最大允许30次请求
        image_with_summary_list = []

        for image_with_context in image_with_context_list:
            current_time = time.time()
            # 调用大模型生成摘要
            # 滑动窗口限流逻辑
            # 进入循环，先清理窗口内超过60秒的历史请求时间戳，释放配额
            while dq and current_time - dq[0] > 60:
                dq.popleft()
                current_time = time.time()

            # 有两种情况 如果队列中所有请求都在60秒窗口内没有过期/队列中有过期记录被清理
            # 判断窗口内请求数量是否达到上限，已满则阻塞等待，未满直接放行
            # 如果dq存在且窗口已满，需要等待最早的请求超时释放配额
            if dq and len(dq) == dq.maxlen:
                current_time = time.time()
                need_wait_time = 60 - (current_time - dq[0])
                if need_wait_time > 0:
                    time.sleep(need_wait_time)  # 阻塞等待窗口滑动
                current_time = time.time()
                while dq and current_time - dq[0] > 60:
                    dq.popleft()

            # 当前请求通过限流校验，记录本次请求时间戳，用于后续窗口计数判断
            # 写入时间戳用于统计窗口内总请求次数，维持滑动窗口限流效果
            dq.append(current_time)

            #  有空位 可以入列 使用base64 优势减少http请求数
            with open(image_with_context.get("image_path"), "rb") as f:
                image_data = f.read()
                base64_str = base64.b64encode(image_data).decode("utf-8")
                #小图片才可以使用，模型要求的是图片转为base64格式
                #base64是一种将二进制数据转为纯文本字符的编码方式，让数据再文本协议中安全传输

            # 给大模型发请求
            # 构造提示词：参考阿里云百炼提供的提示词
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
            result = llm.invoke(input=messages)

            image_with_summary_list.append({
                "image_name": image_with_context.get("image_name"),
                "image_path": image_with_context.get("image_path"),
                "summary": result.content
            })

        return image_with_summary_list

    def get_image_with_summary_and_url_list(self, image_with_summary_list):
        """
        批量幂等清理Minio指定目录旧图片，上传新图片并拼接访问链接，返回携带图片url的完整图片信息列表
        :param image_with_summary_list: 待上传图片原始信息列表，每个元素包含image_name图片文件名、image_path本地图片路径、summary图片描述等字段
        :return: list[dict] 原始图片字典+新增url外网访问地址的组合字典列表
        """
        # 定义Minio桶内图片存储目录前缀
        upload_dir = MinIoConfig.minio_img_dir
        # 获取Minio客户端连接实例
        minio_client = get_minio_client()

        # 幂等性删除当前目录下全部历史图片，避免旧图残留
        # 1.遍历桶内指定前缀目录下所有文件，recursive=True递归遍历所有子目录图片
        old_image_list = minio_client.list_objects(bucket_name=MinIoConfig.minio_bucket_name, prefix=upload_dir,
                                                   recursive=True)

        # 2.组装Minio批量删除所需的DeleteObject对象数组
        delete_image_list = [DeleteObject(obj.object_name) for obj in old_image_list]
        # 执行批量删除文件
        errors = minio_client.remove_objects(
            bucket_name=MinIoConfig.minio_bucket_name,
            delete_object_list=delete_image_list
        )
        # 打印文件删除异常日志
        for error in errors:
            print(f"error occurred when deleting object{error}")

        # 初始化结果存储列表，存放上传完成带链接的图片数据
        image_with_summary_and_url_list = []
        # 循环上传每一张本地图片至Minio对象存储
        for image_with_summary in image_with_summary_list:
            # 本地文件上传至Minio指定路径
            minio_client.fput_object(
                bucket_name=MinIoConfig.minio_bucket_name,
                # 拼接桶内完整对象路径：目录前缀/图片文件名
                object_name=upload_dir + "/" + image_with_summary.get("image_name"),
                file_path=image_with_summary.get('image_path'),
            )
            # 拼接图片完整外网访问URL地址
            url = f"http://{MinIoConfig.minio_endpoint}/{MinIoConfig.minio_bucket_name}/{upload_dir}/{image_with_summary.get('image_name')}"
            print(url)
            # 合并原始图片字典与访问url，加入结果集合
            image_with_summary_and_url_list.append({
                **image_with_summary,
                "url": url
            })
        return image_with_summary_and_url_list

    def replace_md_image(self, image_with_summary_and_url_list, md_path_obj, md_content):
        """
        正则匹配Markdown原文中的图片语法，替换为Minio线上图片链接+自定义图片描述
        :param image_with_summary_and_url_list: 上传完成、携带url与summary的图片信息数组
        :param md_path_obj: Markdown文件路径对象（方法内未使用，预留扩展）
        :param md_content: 原始Markdown文本内容
        :return: str 替换图片链接后的全新Markdown文本
        """
        for image_with_summary_and_url in image_with_summary_and_url_list:
            # 正则匹配Markdown图片语法 ![任意文本](任意路径/图片文件名)，对文件名做转义规避特殊字符匹配失效
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_with_summary_and_url.get("image_name")) + r"\)")
            # 全局替换旧图片标签为「![图片描述](线上图片URL)」标准MD图片格式
            # md_content = pattern.sub(
            #     f"![{image_with_summary_and_url.get('summary')}]({image_with_summary_and_url.get('url')})",
            #     md_content)
            md_content = pattern.sub(
                lambda _: f"![{image_with_summary_and_url.get("summary")}]({image_with_summary_and_url.get("url")})",md_content
            )
        # 备份替换摘要和url后的md_content 中去，生成新md文件
        new_md_path_obj = md_path_obj.parent / str(md_path_obj.stem + "_new.md")
        with open(new_md_path_obj, "w", encoding="utf-8") as f:
            f.write(md_content)
        return new_md_path_obj,md_content

    def process(self, state: ImportGraphState):
        """
        节点主流程执行入口
        步骤1：校验MD文件路径并读取文档内容
        步骤2：判断同级images图片目录是否存在，不存在直接返回原文
        步骤3：图片目录为空直接返回原文
        步骤4：提取图片上下文信息
        步骤5：滑动窗口限流调用视觉模型生成图片摘要并返回结果
        :param state: 链路状态入参
        :return: 无图片返回{"md_content":原文}，有图片返回图片摘要结构化数据
        """
        # 第一大步 获取md的路径对象和内容和文件判断
        md_path_obj, md_content = self.check_path(state)

        # 判断图片存储路径是否存在，如果不存在则直接返回md_content不对图片处理
        image_name_path_dir_obj = md_path_obj.parent / "images"
        if not image_name_path_dir_obj.exists():
            return {
                "md_content": md_content
            }

        # 判断图片目录中有没有内容
        image_name_list = os.listdir(image_name_path_dir_obj)
        if not image_name_list:
            logger.info("图片目录为空")
            return {
                "md_content": md_content
            }

        # 走到这意味着存储图片的目录存在，接下来去拿到图片名字列表
        # 第二大步：获取图片的上下文列表，根据图片正则拿到图片位置，获取上下文
        image_with_context_list = self.get_image_with_context_list(image_name_list, image_name_path_dir_obj, md_content)

        # 第三大步:根据第二步得到的上下文图片列表，进行大模型调用真正生成摘要，形成新的图片字典列表
        image_with_summary_list = self.get_image_with_summary_list(image_with_context_list)

        #第四大步:上传图片到minio，自己构造图片的线上url ,最后将url放到字典列表中
        image_with_summary_and_url_list = self.get_image_with_summary_and_url_list(image_with_summary_list)
        #第五大步:替换md当中的图片
        new_md_path_obj,md_content  = self.replace_md_image(image_with_summary_and_url_list,md_path_obj,md_content)
        return {
            "md_content":md_content,
            "md_path":str(md_path_obj)
        }



if __name__ == '__main__':
    """
    主程序测试入口
    单独运行该文件测试图片解析节点完整逻辑
    """
    node = NodeMdImage()
    init_state = {
        "md_path": r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册\hak180产品安全手册.md"
    }
    result = node(init_state)
    print(result)