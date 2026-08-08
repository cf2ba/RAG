import os
from dotenv import load_dotenv
#防止环境变量中的api_key覆盖
#override  = True 说的是.env文件当中和系统环境变量同名的配置，是否会覆盖系统环境变量
#如果是True, .env会覆盖系统环境变量，默认为False 代表.env的配置不会覆盖系统环境变量
load_dotenv(override=True) #这个api方法会自动爬楼一层层去找项目中的.env文件，并加载其中的环境变量


#如果嵌入过深用绝对路径加载.env #拼接
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path=env_path,override=True)


print(os.path.dirname(os.path.abspath(__file__)))
class MineruToken:
    mineru_token = os.getenv('MINERU_TOKEN')
class LLMConfig:
    openai_api_key = os.getenv('OPENAI_API_KEY')
    openai_base_url = os.getenv('OPENAI_BASE_URL')
    llm_default_model = os.getenv('LLM_DEFAULT_MODEL')
    # 默认温度参数（0-1，越低越稳定）
    llm_default_temperature = float(os.getenv('LLM_DEFAULT_TEMPERATURE'))
    # 视觉语言模型
    vl_model = os.getenv('VL_MODEL')
    # 商品名识别模型
    item_model = os.getenv('ITEM_MODEL')

class MinIoConfig:
    # MinIO 服务端点
    minio_endpoint = os.getenv('MINIO_ENDPOINT')
    # 访问密钥
    minio_access_key = os.getenv('MINIO_ACCESS_KEY')
    # 私有密钥
    minio_secret_key = os.getenv('MINIO_SECRET_KEY')
    # 存储桶名称
    minio_bucket_name = os.getenv('MINIO_BUCKET_NAME')
    # 图片上传目录
    minio_img_dir = os.getenv('MINIO_IMG_DIR')

class EmbeddingConfig:
    # BGE Embedding Models
    # ====================
    # BGE-M3 模型本地路径（根据下载模型的成功提示来设置）
    bge_m3_path = os.getenv("BGE_M3_PATH")
    # bge-m3 模型名称
    bge_m3 = os.getenv("BGE_M3 ")
    # 嵌入模型运行设备，cuda:0表示使用第1块gpu，cpu表示使用cpu，cuda:n表示第n+1块gpu
    bge_device = os.getenv("BGE_DEVICE")
    # 是否使用半精度（true/false）1=开启（gpu加速更高效），0=关闭（兼容低版本gpu/cpu）
    bge_fp16 =True if os.getenv("BGE_FP16 ") in("True",1,True,"1") else False
class MilvusConfig:
    milvus_url = os.getenv("MILVUS_URL")
    # 知识库切片集合名
    chunks_collection = os.getenv("CHUNKS_COLLECTION")
    # 商品名称集合名
    item_name_collection = os.getenv("ITEM_NAME_COLLECTION")
if __name__ == '__main__':
    print(os.getenv("BGE_FP16"),type(os.getenv("BGE_FP16")))
    # print(bool(os.getenv("BGE_FP16")))