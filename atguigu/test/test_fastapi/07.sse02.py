import asyncio
from tokenize import generate_tokens

import uvicorn
from fastapi import FastAPI, Body, Path
from pydantic import Field, BaseModel
from starlette.background import BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
#异步队列不会阻塞
from asyncio import Queue

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#路径参数
@app.get("/")
def index():
    return {"message":"hello"}
class BodyParams(BaseModel):
    query:str = Field(...,description="问题")
    session_id:str = Field(...,description="会话id")

queue_dict = {}
#异步队列的操作都是异步操作，所以需要协程
async def make_answer(query,session_id):
    if not queue_dict.get(session_id):
        queue_dict[session_id] = Queue()
    q = queue_dict[session_id]
    await q.put("我")
    await q.put("是")
    await q.put("小")
    await q.put("助")
    await q.put("手")
    await q.put(None)



@app.post("/sse02")
async def sse02(background_tasks:BackgroundTasks,body_params:BodyParams=Body(...,description="请求体参数")):
    background_tasks.add_task(make_answer,body_params.query,body_params.session_id)
    # print(body_params.query)
    # print(body_params.session_id)
    return {"msg":"收到，准备开始造查询问题"}


async def generate_answer(session_id):
    while not queue_dict.get(session_id):
        await asyncio.sleep(1)
    q = queue_dict[session_id]
    while True:
        msg = await q.get()
        yield f"data:{msg}\n\n"
        await asyncio.sleep(1)
        if msg is None:
            break

@app.get("/stream/{session_id}")
async def stream_answer(session_id:str=Path(...,description="会话id")):
    return StreamingResponse(generate_answer(session_id),media_type="text/event-stream")





if __name__ == '__main__':
    uvicorn.run(app=app,host="0.0.0.0",port=8000)
