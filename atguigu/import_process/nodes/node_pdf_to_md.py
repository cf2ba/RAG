# atguigu/import_process/nodes/node_pdf_to_md.py
import time
# 预加载（提前导入后续用到的模块）
from pathlib import Path
from atguigu.config.config import MineruToken
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format_tool
from atguigu.tool.logger import logger


class NodePDFToMD(NodeBase):
    """
    PDF 转 Markdown 节点：PDF结构化解析
    """

    name = "node_pdf_to_md"

    def check_path(self, state):
        # 防御性编程，
        # 判断路径是否存在
        pdf_path = state.get('local_file_path', '')
        if not pdf_path:
            logger.error("未提供pdf路径")
            raise ValueError("未提供pdf路径")
        pdf_path_obj = Path(pdf_path)
        # 判断文件是否存在
        if not pdf_path_obj.exists():
            logger.error("pdf文件不存在")
            raise ValueError("pdf文件不存在")
        # 判断输出目录是否存在，如果不存在则创建
        local_dir = state.get('local_dir', '')
        if not local_dir:
            logger.error("未提供输出目录路径")
            raise ValueError("未提供输出目录路径")
        local_dir_obj = Path(local_dir)
        if not local_dir_obj.exists():
            local_dir_obj.mkdir(parents=True, exist_ok=True)
        return pdf_path, pdf_path_obj, local_dir_obj

    # 上传pdf到mineru
    def upload_pdf(self, pdf_path, pdf_path_obj):
        import requests
        token = MineruToken.mineru_token
        url = "https://mineru.net/api/v4/file-urls/batch"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files": [
                {"name": f"{pdf_path_obj.name}", "data_id": "abcd"}
            ],
            "model_version": "vlm"
        }
        file_path = [f"{pdf_path}"]
        # 遇到发送请求，要进行三层判断
        # 1.请求是否成功
        response = requests.post(url, headers=header, json=data)
        #数据请求错误查看是什么原因
        response_text = response.text
        logger.info(f"API 响应原始内容: {response_text}")
        if response.status_code != 200:
            logger.error("上传pdf失败")
            raise Exception(f"上传pdf文件请求失败:{pdf_path}")
        logger.info("上传pdf文件请求成功")
        result = response.json()
        # 2.请求数据是否成功
        if result["code"] != 0:
            logger.error("上传pdf文件请求数据失败")
            raise Exception("上传pdf文件请求数据失败")
        logger.info("上传pdf文件请求数据成功")

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]
        for i in range(0, len(urls)):
            with open(file_path[i], 'rb') as f:
                res_upload = requests.put(urls[i], data=f)
                # 3.请求数据结果是否符合预期
                if res_upload.status_code == 200:
                    logger.info(f"{urls[i]} 上传成功")
                else:
                    logger.info(f"{urls[i]} 上传失败")
        return batch_id

    def get_md_zip_url(self,batch_id):
        import requests

        token = MineruToken.mineru_token
        batch_id = batch_id
        url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        #发请求，三层判断轮询
        #1.请求是否成功
        total_time = 300
        use_time = 0
        while True:
            start_time = time.time()
            try:

                res = requests.get(url, headers=header)
                if res.status_code != 200:
                    logger.error("获取pdf文件处理结果请求失败")
                    raise Exception("获取pdf文件处理结果请求失败")
                result = res.json()
                if result["code"] != 0:
                    logger.error("获取pdf文件处理结果请求数据失败")
                    raise Exception("获取pdf文件处理结果请求数据失败")
                data = result["data"]['extract_result'][0]
                if data["state"] != "done":
                    logger.info("pdf文件处理中")
                    raise Exception("pdf文件处理中")
                md_zip_url = data["full_zip_url"]
                return md_zip_url
            except Exception as e:
                logger.error(f"pdf文件处理异常，等待重试{e}")
                end_time = time.time()
                use_time += end_time - start_time
                if use_time > total_time:
                    raise Exception(f"pdf文件处理超时，稍后再试")
                continue
    def download_pdf(self, md_zip_url,local_dir_obj,pdf_path_obj):
        import requests
        response =requests.get(md_zip_url,verify=False,timeout=60)
        #发送请求，三层考虑（请求/请求数据/请求结果），
        if response.status_code != 200:
            logger.error("下载pdf文件处理结果zip压缩包请求失败")
            raise Exception("下载pdf文件处理结果zip压缩包请求失败")
        #因为这次的数据内容是直接放在请求回来的响应对象上的，所以我们只需要做一层考虑
        md_zip_content = response.content
        # print(md_zip_content)
        #获取到的是zip的内容，并不是直接变成zip文件，我们需要同各国文件流操作把这个内容写入磁盘文件
        #pdf_path_obj.stem只有文件前缀无后缀 .name会有后缀
        md_zip_path_obj = local_dir_obj/f"{pdf_path_obj.stem}.zip"
        with open(md_zip_path_obj, 'wb') as f:
            f.write(md_zip_content)
        #解压文件
        import zipfile
        import shutil
        unzip_file_content = zipfile.ZipFile(md_zip_path_obj)
        #解压位置，构造解压的目的地路径 一个非压缩的文件夹
        unzip_file_path_obj = local_dir_obj/f"{pdf_path_obj.stem}"
        #判断解压的目录是否存在，如果存在先删除后创建
        if unzip_file_path_obj.exists():
            #幂等性删除，递归删除 相同的删除请求，无论执行 1 次、10 次、N 次，系统最终状态完全一致，不会产生额外脏数据、重复业务逻辑、异常报错，
            shutil.rmtree(unzip_file_path_obj)
        unzip_file_path_obj.mkdir(parents=True,exist_ok=True)
        #把解压的内容，放到这个目录
        unzip_file_content.extractall(unzip_file_path_obj)
        #解压完成后重命名full.md文件改名未我们原来pdf文件名的前缀.md
        origin_md_path_oobj = unzip_file_path_obj/"full.md"
        #with_name只是在内存中修改了
        new_md_path_obj = origin_md_path_oobj.with_name(f"{pdf_path_obj.stem}.md")
        #在磁盘中修改
        origin_md_path_oobj.rename(new_md_path_obj)

        #读取markdown文件的内容存放在state中
        with open(new_md_path_obj,'r',encoding='utf-8') as f:
            md_content = f.read()
        return md_content,new_md_path_obj


    def process(self, state: ImportGraphState):

        # 先对路径及文件进行校验 #元组解包
        pdf_path,pdf_path_obj,local_dir_obj = self.check_path(state)
        # 上传pdf文件到mineru
        batch_id = self.upload_pdf(pdf_path,pdf_path_obj)
        # 等待mineru解析处理完成文件，轮询，获得一个压缩包zip的url路径
        md_zip_url = self.get_md_zip_url(batch_id)
        # 下载zip文件解压文件，对full.md文件重命名，读取文件内容保存state：md_content，保存到磁盘
        md_content,new_md_path_obj = self.download_pdf(md_zip_url,local_dir_obj,pdf_path_obj)

        return {
            "md_path":str(new_md_path_obj),
            "md_content":md_content,
        }


if __name__ == '__main__':
    node = NodePDFToMD()
    init_state = {'local_file_path': r"C:\Users\CC\OneDrive\桌面\Output\hak180产品安全手册.pdf",
                  'local_dir':  r"C:\Users\CC\OneDrive\桌面\Output"}
    result = node(init_state)
    logger.info(json_format_tool(result))
