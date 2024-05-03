import os
import pytest
import sqlite3
import logging
from fastapi.testclient import TestClient
from src.api.config import MASTER_KEY
from src.api.main import app, auth
import tempfile

client = TestClient(app)


@pytest.fixture(scope="module")
def db():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "users.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)")
        yield conn
        conn.close()


@pytest.fixture(scope="module")
def auth_token(db):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)", ("testuser", "testpass")
    )
    db.commit()

    response = client.post(
        "/auth", params={"username": "testuser", "password": "testpass"}
    )
    return response.json()["access_token"]


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"info": "WhisperX API"}


def test_create_user_endpoint(db):
    response = client.post(
        "/create_user",
        params={
            "master_key": MASTER_KEY,
            "username": "testuser",
            "password": "testpass",
        },
    )
    assert response.status_code == 200


def test_auth_endpoint(db):
    response = auth("testuser", "testpass")
    assert response["access_token"]


def test_create_transcription_job(auth_token):
    files = {"file": open("/home/namastex/whisperx-api/data/test.mp4", "rb")}
    response = client.post(
        "/jobs", files=files, headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert "task_id" in response.json()
    assert response.json()["status"] == "PENDING"


def test_list_jobs(auth_token):
    response = client.get("/jobs", headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 200


def test_get_job_status(auth_token):
    files = {"file": open("/home/namastex/whisperx-api/data/test.mp4", "rb")}
    create_response = client.post(
        "/jobs", files=files, headers={"Authorization": f"Bearer {auth_token}"}
    )
    task_id = create_response.json()["task_id"]

    response = client.get(
        f"/jobs/{task_id}", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200


def test_stop_job(auth_token):
    files = {"file": open("/home/namastex/whisperx-api/data/test.mp4", "rb")}
    create_response = client.post(
        "/jobs", files=files, headers={"Authorization": f"Bearer {auth_token}"}
    )
    task_id = create_response.json()["task_id"]

    response = client.post(
        f"/jobs/{task_id}/stop", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "STOPPED"
