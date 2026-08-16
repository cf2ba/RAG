import shutil
import uuid

import uvicorn
from fastapi import FastAPI, Path, Query, Depends, UploadFile, File, Body
from pydantic import BaseModel
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

app = FastAPI()
#路径参数
@app.get("/")
def index():
    return {"message":"hello"}
#JsonResponse 返回的数据都是json格式，只是返回的时候需要额外的数据
@app.get("/api/user")
async def get_user():    # 等价于直接
    # return {"name": "张三", "age": 20}#（FastAPI 自动转 JSONResponse）
    return JSONResponse(
        content={
            "code":20000,
            "data":{"name": "张三", "age": 20},
        },
        status_code=200,# 可选，默认 200
        headers={"X-Custom-Header": "custom-value"})  # 可选，自定义响应头    )
#请求头的信息是



#前后端不分离(不会出现跨域） 同一个服务器 同源 ip端口一致
#1.前端文件和后端代码文件在一起（代码在一起）
#2.前端部署和后端部署在一起（部署在一起）
#3.浏览器看到的页面其实是后端接口返回去的数据（前端的页面协议、ip、端口和后端服务器一致）

#前后端分离
#1.前端文件和后端代码文件不在一起（代码不一起）
#2.前端部署和后端部署不在一起（部署不在一起） 前后端服务器不同 ，浏览器先显示前端服务器再显示后端
#3.前端负责渲染数据到页面，前后端页面协议、ip、端口不一样，请求发的是ajax请求，会出现跨域
#http请求不分离基本都是普通请求，普通请求和ajax请求（区别就是看浏览器刷新不刷新  不刷新ajax请求）
#普通请求 不跨域  前后端不分离
#前后端是一个localhost一个是127.0.0.1也算跨域
#ajax请求  跨域  前后端分离  fetch（）发送请求









if __name__ == '__main__':
    uvicorn.run(app,host='0.0.0.0',port=8000)