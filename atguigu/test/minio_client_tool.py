from minio import Minio

minio_client = None
def minio_client_init():
    global minio_client
    #创建一个minio代理
    if minio_client is None:
        minio_client = Minio(

        )

        #创建桶
        if not minio_client.bucket_exists():
            minio_client.make_bucket()
