from fastapi import FastAPI, Depends, HTTPException, Query, Form, UploadFile
from fastapi.security import HTTPBearer, OAuth2PasswordBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse

import os
import dotenv
import subprocess
import sqlite3
import logging
import jwt
from datetime import datetime
from enum import Enum
from celery import states
from celery.exceptions import Ignore
from celery import Celery, Task
from utils import convert_to_mp3, create_directories, read_output_files, run_whisperx, save_uploaded_file

# Load environment variables
dotenv.load_dotenv()

# Initialize FastAPI and logging
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

# Environment Variables
SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")
MASTER_KEY = os.getenv("MASTER_KEY", "master_key")
HF_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
API_PORT = os.getenv("API_PORT", 11300)
API_HOST = os.getenv("API_HOST", "localhost")
BROKER_URL = os.getenv("RABBIT_MQ_URI", "amqp://guest:guest@localhost:5672//")

# Initialize Celery
celery_app = Celery('whisperx-tasks', backend='db+sqlite:///celery.db', broker=BROKER_URL)

# Initialize security
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth", auto_error=False)

class LanguageEnum(str, Enum):
    pt = "pt"
    en = "en"
    es = "es"
    fr = "fr"
    it = "it"
    de = "de"

class ModelEnum(str, Enum):
    tiny = "tiny"
    small = "small"
    base = "base"
    medium = "medium"
    largeV2 = "large-v2"
    largeV3 = "large-v3"

class ResponseTypeEnum(str, Enum):
    json = "json"
    file = "file"

# Database functions
def get_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)"
    )
    conn.commit()
    return conn, cursor

# JWT functions
def create_jwt_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def decode_jwt_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Signature has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Dependency for authentication
async def get_current_user(authorization: HTTPAuthorizationCredentials = Depends(security)):
    token = authorization.credentials
    try:
        payload = decode_jwt_token(token)
        return payload
    except:
        raise HTTPException(status_code=403, detail="Forbidden")

# Celery task for transcription
@celery_app.task(name="transcribe_file")
def transcribe_file(temp_video_path, lang, model, min_speakers, max_speakers):
    try:
        temp_mp3_path = convert_to_mp3(temp_video_path)
        run_whisperx(temp_mp3_path, lang, model, min_speakers, max_speakers)
        output_files = read_output_files()
        result = {
            "status": "success",
            "vtt_content": output_files["vtt_content"],
            "txt_content": output_files["txt_content"],
            "json_content": output_files["json_content"],
            "srt_content": output_files["srt_content"],
            "vtt_path": output_files["vtt_path"],
            "txt_path": output_files["txt_path"],
            "json_path": output_files["json_path"],
            "srt_path": output_files["srt_path"]
        }
        return result
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise e

# API Endpoints
@app.get("/")
def read_root():
    return {"info": "WhisperX API"}

@app.post("/auth")
def auth(username: str, password: str):
    conn, cursor = get_db()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] == password:
        return {"access_token": create_jwt_token({"sub": username}), "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/create_user")
def create_user(username: str, password: str, master_key: str = Query(...)):
    if master_key != MASTER_KEY:
        return JSONResponse(status_code=403, content={"detail": "Not authorized"})
    conn, cursor = get_db()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return {"detail": "User created successfully"}
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse(status_code=400, content={"detail": "Username already exists"})

@app.post("/jobs")
async def create_transcription_job(
    current_user: dict = Depends(get_current_user),
    lang: LanguageEnum = Form(LanguageEnum.pt, description="Language for transcription"),
    model: ModelEnum = Form(ModelEnum.largeV3, description="Model for transcription"),
    min_speakers: int = Form(1, description="Minimum number of speakers"),
    max_speakers: int = Form(2, description="Maximum number of speakers"),
    file: UploadFile = None,
):
    try:
        create_directories()
        temp_video_path = save_uploaded_file(file)
        task = transcribe_file.delay(temp_video_path, lang, model, min_speakers, max_speakers)
        return {"task_id": task.id, "status": "PENDING"}
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs")
async def list_jobs(current_user: dict = Depends(get_current_user)):
    tasks = celery_app.control.inspect().active()
    jobs = []
    for worker, task_list in tasks.items():
        for task in task_list:
            jobs.append({"task_id": task["id"], "status": task["state"]})
    return jobs

@app.get("/jobs/{task_id}")
async def get_job_status(task_id: str, current_user: dict = Depends(get_current_user)):
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
async def stop_job(task_id: str, current_user: dict = Depends(get_current_user)):
    celery_app.control.revoke(task_id, terminate=True)
    return {"task_id": task_id, "status": "STOPPED"}

if __name__ == "__main__":
    import uvicorn
    from multiprocessing import Process

    def start_celery_worker():
        subprocess.run(["celery", "-A", "api_whisperx.celery_app", "worker", "--loglevel=info"])

    celery_process = Process(target=start_celery_worker)
    celery_process.start()

    uvicorn.run(app, host=API_HOST, port=int(API_PORT))