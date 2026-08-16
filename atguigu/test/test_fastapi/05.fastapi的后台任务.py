#后台任务的作用让用户发请求，立即响应
#中间的一些耗时操作，交给后台去执行
#我们看起来请求已经结束了，但是后台还在执行任务
import time

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import JSONResponse

app = FastAPI()
#路径参数
@app.get("/")
def index():
    return {"message":"hello"}


def generate_love(n,name):
    while n > 0:
        n-=1
        print(f"love{name}")
        time.sleep(1)

@app.get("/testbackgroundtasks")
async def testbackgroundtasks(backgroundtasks:BackgroundTasks):
    backgroundtasks.add_task(generate_love,10,"cc")
    return {"message":"hello world"}

if __name__ == '__main__':
    uvicorn.run(app=app,host="0.0.0.0",port=8000)
