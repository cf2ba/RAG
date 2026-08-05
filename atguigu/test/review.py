# def get_image_with_summary_and_url_list(self, image_with_summary_list):
#     upload_dir = MinIoConfig.minio_img_dir  # 上传到哪个目录
#     minio_client = get_minio_client()
#     # 幂等性删除这个目录中的图片
#     # 1.拿到桶当中这个目录当中的所有老图片（prefix = upload_dir 代表桶下面的目录，不到文件） recursive作用是遍历子目录
#     old_image_list = minio_client.list_objects(bucket_name=MinIoConfig.minio_bucket_name, prefix=upload_dir,
#                                                recursive=True)
#     # for item in old_image_list:
#     #     print(item)
#     # print(old_image_list)
#     # 2.调用api 批量删除老的图片，delete_object_list这个参数要求必须是DeleteObject对象列表
#     # 我们就把上面的图片转化为这个图片列表
#     delete_image_list = [DeleteObject(obj.object_name) for obj in old_image_list]
#     errors = minio_client.remove_objects(
#         bucket_name=MinIoConfig.minio_bucket_name,
#         delete_object_list=delete_image_list
#     )
#     for error in errors:
#         print(f"error occurred when deleting object{error}")
#     # 准备上传图片
#     image_with_summary_and_url_list = []
#     for image_with_summary in image_with_summary_list:
#         minio_client.fput_object(
#             bucket_name=MinIoConfig.minio_bucket_name,
#             # 除了桶之外的路径一直到图片  拼接路径 字符串
#             object_name=upload_dir + "/" + image_with_summary.get("image_name"),
#             file_path=image_with_summary.get('image_path'),
#         )
#         url = f"http://{MinIoConfig.minio_endpoint}/{MinIoConfig.minio_bucket_name}/{upload_dir}/{image_with_summary.get('image_name')}"
#         print(url)
#         image_with_summary_and_url_list.append({
#             **image_with_summary,
#             "url": url
#         })
#     return image_with_summary_and_url_list
#
#
# def replace_md_image(self, image_with_summary_and_url_list, md_path_obj, md_content):
#     for image_with_summary_and_url in image_with_summary_and_url_list:
#         pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_with_summary_and_url.get("image_name")) + r"\)")
#         # 当碰到特殊字符\s时必须使用lambda 来进行替换 ，lambad可以规避特殊字符，特殊字符也可以替换成功
#         md_content = pattern.sub(
#             f"![{image_with_summary_and_url.get("summary")}]({image_with_summary_and_url.get('url')})",
#             md_content)
