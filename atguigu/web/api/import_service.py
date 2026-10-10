import shutil
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import fastapi
import uvicorn
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware

from atguigu.config.config import MinIoConfig
from atguigu.import_process.main_graph import MainGraphRun
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.task_utils import (
    TASK_STATUS_PROCESSING,
    TASK_STATUS_FAILED,
    TASK_STATUS_COMPLETED,
    add_running_task,
    add_done_task,
    update_task_status,
    get_task_info,
    set_task_result,
)

app = FastAPI(
    title="掌柜智库导入模块对应的接口服务",
    description="导入模块各个api接口服务",
    version="0.0.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_main_graph(task_id: str, local_dir: str, local_file_path: str, metadata: dict = None):
    """
    后台执行主图，完成后从最终状态提取元数据并保存。
    """
    try:
        init_state = {
            "task_id": task_id,
            "local_dir": local_dir,
            "local_file_path": local_file_path
        }
        if metadata:
            init_state.update(metadata)

        update_task_status(task_id, TASK_STATUS_PROCESSING)

        # 执行主图，获取最终状态
        final_state = MainGraphRun.creative_run(init_state)

        # --- 从最终状态中提取元数据（取自 chunks 第一条记录） ---
        chunks = final_state.get("chunks", [])
        extracted_meta = {
            "content_type": "",
            "region": "",
            "doc_name": "",
            "topics": "",
            "source_url": "",
        }
        if chunks and len(chunks) > 0:
            sample = chunks[0]
            for key in extracted_meta.keys():
                extracted_meta[key] = sample.get(key, "")

        # 将元数据存入任务结果
        set_task_result(task_id, "metadata", extracted_meta)

        update_task_status(task_id, TASK_STATUS_COMPLETED)

    except Exception as e:
        logger.exception(f"主图执行失败 task_id={task_id}: {e}")
        set_task_result(task_id, "error", str(e))
        set_task_result(task_id, "traceback", traceback.format_exc())
        update_task_status(task_id, TASK_STATUS_FAILED)


@app.post("/upload")
async def upload_file(
        background_task: BackgroundTasks,
        file: UploadFile = File(..., description="上传的文件对象"),
):
    """
    接收文件，保存本地并备份至 MinIO，然后启动后台主图任务。
    """
    task_id = str(uuid.uuid4())

    # 记录上传开始
    start_time = time.time()
    add_running_task(task_id, "upload_file")

    # 保存到本地
    local_dir = rf"C:\Users\CC\OneDrive\桌面\output\{datetime.now().strftime('%Y%m%d')}"
    local_dir_obj = Path(local_dir)
    if not local_dir_obj.exists():
        local_dir_obj.mkdir(parents=True, exist_ok=True)
    local_file_path = str(local_dir_obj / file.filename)

    with open(local_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f, 1024 * 1024)
    logger.info(f"文件上传成功，保存路径为 {local_file_path}")

    # 备份至 MinIO
    minio_client = get_minio_client()
    minio_client.fput_object(
        bucket_name=MinIoConfig.minio_bucket_name,
        object_name=f"pdf_file/{datetime.now().strftime('%Y%m%d')}/{task_id}/{file.filename}",
        file_path=local_file_path
    )
    logger.info(f"文件上传到 MinIO 成功，路径: pdf_file/{datetime.now().strftime('%Y%m%d')}/{task_id}/{file.filename}")

    add_done_task(task_id, "upload_file")

    # 启动后台任务（不再传递前端元数据，由主图内部自动提取）
    background_task.add_task(
        run_main_graph,
        task_id=task_id,
        local_dir=local_dir,
        local_file_path=local_file_path,
        metadata=None
    )

    # 立即返回 task_id，元数据字段为空（后续通过 /status 获取）
    return {
        "task_id": task_id,
        "file_size": file.size,
        "file_name": file.filename,
        "metadata": {}   # 占位，实际元数据在处理完成后通过 /status 返回
    }


@app.get("/status/{task_id}")
def get_status(task_id: str = fastapi.Path(..., description="任务ID")):
    """
    查询任务状态，若已完成且包含元数据，则附加到返回体中。
    """
    info = get_task_info(task_id)

    # 如果任务结果中存在 metadata，则提到顶层供前端使用
    if info.get("result") and isinstance(info["result"], dict):
        metadata = info["result"].get("metadata")
        if metadata:
            info["metadata"] = metadata

    return info


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)