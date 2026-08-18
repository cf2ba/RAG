import json
import time
import uuid

import uvicorn
from fastapi import FastAPI, Path, Body
from pydantic import BaseModel, Field
from starlette.background import BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from atguigu.query_process.main_graph import MainGraph
from atguigu.tool.mongodb import get_recent_history_list, clear_history
from atguigu.tool.task_utils import update_task_status, TASK_STATUS_PROCESSING, get_task_info, TASK_STATUS_COMPLETED, \
    TASK_STATUS_FAILED, create_queue, put_data, queue_dict

app = FastAPI(
    title="检索模块对应的接口",
    description="检索模块对应的前端接口",
    version="0.0.1"
)


# 配置跨域中间件，允许前端跨域访问接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 允许所有来源，生产环境建议指定域名
    allow_credentials=True,       # 允许携带cookie凭证
    allow_methods=["*"],          # 允许所有请求方法 GET/POST等
    allow_headers=["*"],          # 允许所有请求头
)
#第一步：写健康检查接口（心跳检查 轮询）
@app.get("/health")
async def health():
    #随便返回，因为前端只是在判断请求是否成功返回的状态码为ok
    return {"aa","bb"}
#第二步:获取历史会话记录接口，前端显示
@app.get("/history/{session_id}")
async def get_history(session_id :str=Path(...,description="会话id")):
    #获取历史记录返回即可
    history_list = get_recent_history_list((session_id))
    # print(session_id)
    history_list = [
        {
            "_id":str(item.get("_id")),
            "role":item.get("role"),
            "text":item.get("text"),
            "item_names":item.get("item_names",""),
            "ts":item.get("ts",""),
            "session_id":item.get("session_id","")
        }
        for item in history_list
    ]
    history_list.sort(key=lambda a: a.get("ts", 0))
    return {"items":history_list}
#返回数据的时候要看前端页面写的是什么，前端已经完成的情况下，返回前端需要的格式


#第三步:前端点击清除历史会话记录，删除接口
#逻辑删除和物理删除  物理删除不删除数据库的内容，逻辑删除是修改
@app.delete("/history/{session_id}")
async def deletet_history(session_id:str=Path(...,description="会话id")):
    clear_history(session_id)
    return {"msg":"删除成功"}




def run_main_graph(task_id,original_query,session_id):
    #造队列
    # if not queue_dict.get(task_id):
    #     queue_dict[task_id]=Queue()  #必须同步
    # q = queue_dict[task_id]
    create_queue(task_id)#创建队列

    try:
        init_state = {
            "task_id":task_id,
            "original_query":original_query,
            "session_id":session_id
        }
        #更新总状态
        update_task_status(task_id,TASK_STATUS_PROCESSING)
        #放到队列中，sse后期可以从队列中取出更新的数据状态，然后推送给前端
        # q.put({"event":"progress","data":get_task_info(task_id)})
        put_data(task_id,event="progerss",data=get_task_info(task_id))
        MainGraph.create_run(init_state)
        update_task_status(task_id, TASK_STATUS_COMPLETED)
        # q.put({"event": "progress", "data": get_task_info(task_id)})
        put_data(task_id,event="progress",data=get_task_info(task_id))

    except Exception as e:
        from atguigu.tool.logger import logger
        logger.info(f"maingraph{task_id}执行失败")
        update_task_status(task_id, TASK_STATUS_FAILED)
        # q.put({"event": "error", "data": get_task_info(task_id)})
        put_data(task_id,event="error",data=get_task_info(task_id))
        raise e
    finally:
        # 无论成功或失败都写入结束哨兵，通知SSE生成器终止，避免生成器无限阻塞导致连接被客户端强制关闭
        put_data(task_id,event="end",data={})

#第四步:查询接口

class QueryParams(BaseModel):
    query:str = Field(...,description="查询")
    session_id:str=Field(...,description="会话id")
@app.post("/query")
async def query(background_tasks :BackgroundTasks,query_params:QueryParams = Body(...,description="查询请求体参数")):
    # print(query_params.query)
    # print(query_params.session_id)
    #创建task_id后期需要追踪
    task_id = str(uuid.uuid4())
    original_query = query_params.query
    session_id = query_params.session_id
    #第五步 调后台接口任务只想graph
    background_tasks.add_task(run_main_graph,task_id,original_query,session_id)
    return {
        "task_id":task_id,
        "original_query":original_query,
        "session_id":session_id,

    }

#流失输出生成器
def generate_stream(task_id):
    while not queue_dict.get(task_id):
        time.sleep(1)
    q = queue_dict[task_id]
    while True:
        item = q.get()
        # 收到结束哨兵则终止流，让StreamingResponse正常结束，避免生成器无限阻塞
        if item.get("event") == "end":
            break
        yield f"event:{item.get("event")}\n"
        yield f"data:{json.dumps(item.get("data"),ensure_ascii=False)}\n\n"
#流失请求对应接口
@app.get("/stream/{task_id}")
async def stream(task_id:str=Path(...,description="任务ID")):
    return StreamingResponse(generate_stream(task_id),media_type="text/event-stream")

if __name__ == '__main__':
    uvicorn.run(app,host="0.0.0.0",port=8001)