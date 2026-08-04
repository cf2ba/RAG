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