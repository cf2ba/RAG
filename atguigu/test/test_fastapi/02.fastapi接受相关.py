import shutil
import uuid

import uvicorn
from fastapi import FastAPI, Path, Query, Depends, UploadFile, File, Body
from pydantic import BaseModel
from pydantic import Field
from starlette.requests import Request

app = FastAPI()
#路径参数
@app.get("/")
def index():
    return {"message":"hello"}
#1.接受路径参数，路径参数是占url的一部分,而且传递了必须占位  浏览器地址栏只对应能发的只有get请求
#Path里面我们关注限定的几个参数 ...代表必须传递 default代表默认值，默认值一般不写default,只写description
@app.get("/testpath/{id}/{name}/{age}",summary="测试路径参数")
def testpath(
        id:int,
        name:str = "aa",#路径参数必须传递，写默认值没有意义
        age:int=Path(...,description="年龄",ge=0,le=120)

):
    return {"id":id,"name":name,"age":age}
#查询参数
@app.get("/testquery")
def testquery(
        id:int,#默认必须传递否则报错
        height:float=80,#默认传递80,可传可不穿
        gender:str=Query(...,description="性别"),#必传
        name:str=Query(default="yangmi",description="姓名") #客串可不传递

):
    return{"id":id,"height":height,"gender":gender,"name":name}

#请求体参数是挑请求方式的，一般get和delete不常用，没人传请求体
#只有post和put才会用到请求体参数
#请求体参数一般都是json ,json前端传递的一般都是对象或者对象的数组(字典或者字典列表/对象或者对象列表）

#请求体的对象一般用BaseModel来接受，BaseModel是pydantic库里面的一个基类，用来做数据校验的，最终是通过这个类的对象去接受参数的
#只要是json请求体参数，BaseModel就是专门针对这些参数的
#1.实例化一个对象
#2.检验传递的json和定义的类中是否匹配
#3.返回实例化对象
class User(BaseModel):
    # username:str
    username:str = Field(...,description="名")
    password:str = Field(default="1111",description="密码")

@app.post("/testbody")
def testbody(user:User):
    print(user,type(user))
    return user


#4.接受混合参数  接受路径/查询/请求体参数一起传递
#使用BaseModel类去解决请求体，使用普通类去解决路径和查询参数（键值对参数）
# @app.post("/testmixed/{id}")
# def testmixed(
#         user:User, #请求体参数
#         id:int=Path(...,description="用户id"), #路径参数
#         name:str=Query(...,description="姓名"),#查询参数
#         age:int=Query(default=19,description="年龄")  #有默认值的必须在没有默认值的形参后边 #查询参数
#     ):
#     return {"id":id,"name":name,"age":age,"user":user}

#接受混合参数，第二种方式
#依赖注入给一个Depends类，使用他传递一个类或者函数（可以调用的东西）
# 会自动去调用传递的类或者函数，并且fastapi会自动识别所有的参数进行自动注入
class Student:
    def __init__(self,id:int=None,name:str=None,age:int=18):
        self.id=id
        self.name=name
        self.age=age
@app.post("/testmixed/{id}")
def testmixed(
        # user:User, #请求体参数
        user:User = Body(...,description="请求体"), #请求体参数
        student:Student=Depends(Student)
    ):
    return {"id":student.id,"name":student.name,"age":student.age,"user":user}



#6.接受请求头的信息   #在headers终自己加一个token
@app.get("/testheader")
def testheader(request:Request): #Request 整个请求报文通过它接受
    print(request.headers.get("token"))
    return {"message":"hello"}


#文件接收 前端上传后端接收   #前端body
#接收formData的数据，文件上传，文件上传是表单提交的一种方式
@app.post("/upload")
def upload(file:UploadFile = File(...,description="上传文件")):
    print(file.filename)
    print(file.size)
    print(file.content_type)
    print(file.file)
    print(file.headers)
    dir_path = "./"
    file_name = str(uuid.uuid4())[:8]+file.filename #全宇宙唯一 生成一个随机的全宇宙唯一的标识是个字符串
    # with open(dir_path,"w",encoding="utf-8")
    fs = open(dir_path + "/" +file_name,"wb")
    shutil.copyfileobj(file.file,fs,1024*1024)#存储图片 ，存大的文件方便
    fs.close()


    #转储minio
    return {"file":file.filename,"url":"后期自己做"}
#上传的图片不会存储到本地服务器 ，这里拿到文件后把文件保存到磁盘，
# 然后把文件转储到对象容器中（minio)










if __name__ == '__main__':
    uvicorn.run(app,host='0.0.0.0',port=8000)