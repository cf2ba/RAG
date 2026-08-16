#WSGI异步服务器  服务器：硬件（电脑） 软件（代码)  电脑上装了某个软件的服务，就称作这个电脑是某个软件的服务器
import uvicorn
from fastapi import FastAPI

app = FastAPI(
    title="test",
    description="这是一个测试的服务号",
    version="0.1.0")
@app.get("/")
def index():
    return{"message":"hello world"}  #默认返回json
if __name__ == '__main__':
    uvicorn.run(app=app,host="0.0.0.0",port=8000)  #host允许访问ip 0.0.0.0所有ip都可访问   /docs测试接口
    #在命令端 uv run uvicorn atguigu.test.test_fastapi.demo:app --reload