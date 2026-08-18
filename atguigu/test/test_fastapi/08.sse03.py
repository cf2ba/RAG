# 案例2 使用post请求 + SSE流式推送完整示例
# 业务流程说明
# 1、前端POST请求，请求体携带 query、session_id 两个参数传给后端
# 2、后端POST接口接收参数，返回响应给前端，同时启动后台异步任务生成消息放入会话独立异步队列
# 3、前端携带session_id发起GET请求订阅SSE长连接
# 4、SSE流式接口根据session_id找到对应消息队列，循环逐个取出消息，通过yield持续推送给前端

import asyncio
import uvicorn
from fastapi import FastAPI, Body, BackgroundTasks, Path
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
# 注意：存在导入覆盖，下方asyncio.Queue会覆盖queue.Queue，项目统一使用异步队列
from queue import Queue
from asyncio import Queue

from starlette.responses import StreamingResponse

# 创建FastAPI应用实例
app = FastAPI()

# 配置跨域中间件，允许前端跨域访问接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 允许所有来源，生产环境建议指定域名
    allow_credentials=True,       # 允许携带cookie凭证
    allow_methods=["*"],          # 允许所有请求方法 GET/POST等
    allow_headers=["*"],          # 允许所有请求头
)

# 请求体参数模型，用于接收POST接口json参数
class BodyParams(BaseModel):
    query: str = Field(..., description="用户查询内容")
    session_id: str = Field(..., description="会话唯一id，用来区分不同前端SSE连接")

# 全局字典：存储每个会话对应的异步消息队列
# key: session_id(str)  value: asyncio.Queue()
queue_dict = {}

async def make_answer(query, session_id):
    """
    【后台异步任务】生成流式消息，写入对应session的异步队列
    Args:
        query: 用户传入的查询文本（当前示例未实际使用，预留业务扩展）
        session_id: 会话唯一标识，绑定独立消息队列
    Logic:
        1. 判断当前session是否存在队列，不存在则新建asyncio异步队列
        2. 依次往队列推入多条流式消息，区分process普通消息与final结束消息
    """
    if not queue_dict.get(session_id):
        queue_dict[session_id] = Queue()
    # 获取当前会话专属消息队列
    q = queue_dict[session_id]

    # 向异步队列逐条推送sse消息单元，包含event事件标识与data数据
    await q.put({"event":"process","data":"我爱杨幂"})
    await q.put({"event":"process","data":"我爱赵丽颖"})
    await q.put({"event":"process","data":"我爱刘诗诗"})
    await q.put({"event":"process","data":"我爱迪丽热巴"})
    await q.put({"event":"process","data":"我爱鞠婧祎"})
    await q.put({"event":"final","data":"我不爱了"})


@app.post("/sse03")
async def sse03(
    background_tasks: BackgroundTasks,
    body_params: BodyParams = Body(..., description="POST请求体JSON参数")
):
    """
    【触发接口】前端调用此POST接口，初始化流式任务
    Args:
        background_tasks: FastAPI内置后台任务对象，接口响应后仍然会执行任务
        body_params: 请求体对象，包含query、session_id
    Return:
        dict 普通json响应，通知前端任务已启动，随后前端发起SSE订阅
    """
    # 将消息生成逻辑加入后台任务，不阻塞当前接口响应

    background_tasks.add_task(make_answer, body_params.query, body_params.session_id)
    return {"msg": "收到,开始查询信息造消息"}


async def generate_answer(session_id):
    """
    【SSE消息生成器】异步生成器，持续从队列读取消息并组装SSE标准格式推送前端
    Args:
        session_id: 会话id，用来定位专属消息队列
    Yield:
        SSE协议标准字符串：event事件 + data数据，以双换行\n\n作为单条消息分隔符
    Logic:
        1. 轮询等待会话队列创建完成
        2. 循环阻塞读取队列消息，组装sse格式逐段返回
        3. 捕获异常，向前端推送error事件
    """
    # 轮询等待：防止SSE连接先建立、后台任务还未创建队列
    while not queue_dict.get(session_id):
        await asyncio.sleep(3)

    q = queue_dict[session_id]
    while True:
        try:
            # 阻塞取出队列内一条消息
            msg = await q.get()
            # 模拟消息推送间隔，模拟真实流式输出效果
            await asyncio.sleep(1)
            # SSE协议规范格式拼接
            yield f"event:{msg.get('event')}\n"
            yield f"data:{msg.get('data')}\n\n"
            # 原逻辑预留终止标识，当前示例没有推送None，保留兼容
            if msg is None:
                break
        except Exception as e:
            # 出现异常向前端推送错误事件
            yield f"event:error\n"
            yield f"data:{e}\n\n"


@app.get("/stream/{session_id}")
async def stream_answer(session_id: str = Path(...,description="会话唯一id，路径参数")):
    """
    【SSE订阅接口】前端长连接订阅流式消息
    Args:
        session_id: 路径参数，会话标识，和POST请求保持一致
    Return:
        StreamingResponse：流式响应，指定媒体类型为SSE标准text/event-stream
    """
    return StreamingResponse(
        generate_answer(session_id),
        media_type="text/event-stream"
    )


if __name__ == '__main__':
    # 启动uvicorn服务
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )