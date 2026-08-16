import uvicorn
from fastapi import FastAPI
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

app = FastAPI()
#路径参数
@app.get("/")
def index():
    return {"message":"hello"}

if __name__ == '__main__':
    uvicorn.run(app=app,host="0.0.0.0",port=8000)
