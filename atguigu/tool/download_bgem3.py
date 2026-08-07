from modelscope.hub.snapshot_download import snapshot_download

# 下载模型到当前目录下的 models/bge-m3 文件夹
#下载下来可能是一个总的目录，这个目录总的目录
model_dir = snapshot_download('BAAI/bge-m3', cache_dir='C:/Users/CC/OneDrive/桌面/Output/ai_models/modelscope_cache/models')
print(f"模型已下载到: {model_dir}")