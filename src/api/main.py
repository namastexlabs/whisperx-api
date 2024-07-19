import logging
import sys
import os
import subprocess
from src.api.config import API_HOST, API_PORT
from fastapi import FastAPI, Depends, HTTPException, Query, Form, UploadFile
from src.api.database import get_db
from src.api.models import LanguageEnum, ModelEnum, ResponseTypeEnum
from src.api.tasks import transcribe_file, celery_app
from src.utils.file_utils import create_directories, save_uploaded_file
from celery import states

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

app = FastAPI(
    title="Whisperx API Wrapper",
    description="Upload a video or audio file and get a transcription in return, max file size is 100MB.",
    version="0.1.2",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)
logging.basicConfig(level=logging.INFO)


@app.get("/")
def read_root():
    return {"info": "WhisperX API"}


@app.post("/auth")
def auth_endpoint(username: str, password: str):
    return auth(username, password)


@app.post("/create_user")
def create_user_endpoint(username: str, password: str, master_key: str = Query(...)):
    return create_user(username, password, master_key)


@app.post("/jobs")
async def create_transcription_job(
        lang: LanguageEnum = Form(LanguageEnum.pt, description="Language for transcription"),
        model: ModelEnum = Form(ModelEnum.largeV3, description="Model for transcription"),
        min_speakers: int = Form(1, description="Minimum number of speakers"),
        max_speakers: int = Form(2, description="Maximum number of speakers"),
        file: UploadFile = None,
):
    try:
        create_directories()
        temp_video_path = save_uploaded_file(file)
        task = transcribe_file.delay(
            temp_video_path, lang, model, min_speakers, max_speakers
        )
        return {"task_id": task.id, "status": "PENDING"}
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def list_jobs():
    tasks = celery_app.control.inspect().active()
    jobs = []
    for worker, task_list in tasks.items():
        for task in task_list:
            jobs.append({"task_id": task["id"], "status": task["state"]})
    return jobs


@app.get("/jobs/{task_id}")
async def get_job_status(task_id: str):
    task_result = celery_app.AsyncResult(task_id)
    if task_result.state == states.PENDING:
        response = {
            "task_id": task_id,
            "status": task_result.state,
        }
    elif task_result.state == states.FAILURE:
        response = {
            "task_id": task_id,
            "status": task_result.state,
            "error": str(task_result.result),
        }
    else:
        response = {
            "task_id": task_id,
            "status": task_result.state,
            "result": task_result.result,
        }
    return response


@app.post("/jobs/{task_id}/stop")
async def stop_job(task_id: str):
    celery_app.control.revoke(task_id, terminate=True)
    return {"task_id": task_id, "status": "STOPPED"}


if __name__ == "__main__":
    import uvicorn
    from multiprocessing import Process


    def start_celery_worker():
        subprocess.run(
            ["celery", "-A", "src.api.tasks.celery_app", "worker", "--loglevel=info"]
        )


    celery_process = Process(target=start_celery_worker)
    celery_process.start()

    uvicorn.run(app, host=API_HOST, port=int(API_PORT))
