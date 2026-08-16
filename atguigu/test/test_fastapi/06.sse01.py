#  	1、客户前端发ajax请求要发邮件并携带session_id，服务端直接回复收到，制造邮件开始
#  	2、服务端就开始执行backgroundtask当中造邮件的函数，造的邮件全部放在队列当中
#  	3、客户端想直接拿到造的邮件内容，造一个拿一个，那么客户端需要去发送订阅sse请求
#  	4、服务端需要写sse回复接口，流式返回，流式返回就是把一个生成器对象返回
#  		生成器函数当中就是从queue_dict当中获取自己session_id的队列，从队列当中一个一个yield球
# 
#  	注意：每个session_id对应自己的邮件队列
import time
from queue import Queue

import uvicorn
from fastapi import FastAPI, Query

from starlette.background import BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

queue_dict = {}
def maker_email(session_id:str):
    global queue_dict
    if not queue_dict.get(session_id):
        queue_dict[session_id] = Queue()
    q = queue_dict.get(session_id)
    q.put("helloword01")
    q.put("helloword02")
    q.put("helloword03")
    q.put("helloword04")
    q.put("helloword05")
    q.put(None)#结束标识
@app.get("/sse01")
async def sse01(
        background_tasks:BackgroundTasks,
        session_id:str=Query(...,description="会话id")):
    background_tasks.add_task(maker_email,session_id=session_id)
    print(session_id)
    return {"message":"收到立马制造邮件"}

@app.get("/stream")
async def stream(session_id:str=Query(...,description="会话id")):
    def get_email():
        while not queue_dict.get(session_id):
            time.sleep(3)
        q = queue_dict.get(session_id)
        while True:
            email = q.get()
            yield f"data:{email}\n\n"
            if email is None:
                break
            time.sleep(1)
    return StreamingResponse(get_email(),media_type="text/event-stream")
if __name__ == '__main__':
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )