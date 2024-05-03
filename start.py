import os
import subprocess
from multiprocessing import Process
from api.config import API_HOST, API_PORT
import uvicorn
from api.main import app

def start_celery_worker():
    subprocess.run(["celery", "-A", "api.tasks.celery_app", "worker", "--loglevel=info"])

if __name__ == "__main__":
    celery_process = Process(target=start_celery_worker)
    celery_process.start()

    uvicorn.run(app, host=API_HOST, port=int(API_PORT))