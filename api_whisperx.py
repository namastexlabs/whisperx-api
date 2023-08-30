from fastapi import FastAPI, Depends, HTTPException, Query, Form, UploadFile
from fastapi.security import HTTPBearer, OAuth2PasswordBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse,  StreamingResponse
from zipfile import ZipFile
from io import BytesIO
import os
import dotenv
import subprocess
import sqlite3
import logging
import jwt
from datetime import datetime
from enum import Enum

# Load environment variables
dotenv.load_dotenv()

# Initialize FastAPI and logging
app = FastAPI(
    title="Whisperx API Wrapper",
    description="Upload a video or audio file and get a transcription in return, max file size is 100MB.",
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)
logging.basicConfig(level=logging.INFO)

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
    large = "large-v2"

class ResponseTypeEnum(str, Enum):
    json = "json"
    file = "file"
    
# Environment Variables
SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")
MASTER_KEY = os.getenv("MASTER_KEY", "master_key")
HF_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
API_PORT = os.getenv("API_PORT", 11300)
API_HOST = os.getenv("API_HOST", "localhost")

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

def create_directories():
    if not os.path.exists('./temp'):
        os.makedirs('./temp')
    if not os.path.exists('./data'):
        os.makedirs('./data')

def save_uploaded_file(file):
    temp_video_path = f"./temp/{file.filename}"
    with open(temp_video_path, "wb") as buffer:
        buffer.write(file.file.read())
    return temp_video_path

def convert_to_mp3(file_path):
    temp_mp3_path = os.path.splitext(file_path)[0] + ".mp3"
    subprocess.run(["ffmpeg", "-y", "-i", file_path, temp_mp3_path], check=True)
    return temp_mp3_path

def run_whisperx(temp_mp3_path, lang, model, min_speakers, max_speakers):
    output_dir = "./data/"
    cmd = f"whisperx {temp_mp3_path} --model {model} --language {lang} --hf_token {HF_TOKEN} --output_format all --output_dir {output_dir}  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers {min_speakers} --max_speakers {max_speakers}"
    subprocess.run(cmd.split(), check=True)

def read_output_files():
    output_dir = "./data/"
    vtt_path = [f for f in os.listdir(output_dir) if f.endswith(".vtt")][0]
    txt_path = [f for f in os.listdir(output_dir) if f.endswith(".txt")][0]

    with open(os.path.join(output_dir, vtt_path), "r") as vtt_file:
        vtt_content = vtt_file.read()

    with open(os.path.join(output_dir, txt_path), "r") as txt_file:
        txt_content = txt_file.read()

    return vtt_content, txt_content, vtt_path, txt_path

def zip_files(vtt_path, txt_path):
    memory_file = BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        zf.write(os.path.join("./data/", vtt_path), vtt_path)
        zf.write(os.path.join("./data/", txt_path), txt_path)
    memory_file.seek(0)
    return memory_file


@app.post("/whisperx-transcribe/")
async def generate_transcription(
    current_user: dict = Depends(get_current_user),
    lang: LanguageEnum = Form(LanguageEnum.pt, description="Language for transcription"),
    model: ModelEnum = Form(ModelEnum.large, description="Model for transcription"),
    min_speakers: int = Form(1, description="Minimum number of speakers"),
    max_speakers: int = Form(2, description="Maximum number of speakers"),
    response_type: ResponseTypeEnum = Query(ResponseTypeEnum.json, description="Type of the response, either 'json' or 'file"),
    file: UploadFile = None,
):
    start_time = datetime.now()

    try:
        create_directories()
        temp_video_path = save_uploaded_file(file)
        temp_mp3_path = convert_to_mp3(temp_video_path)
        run_whisperx(temp_mp3_path, lang, model, min_speakers, max_speakers)
        vtt_content, txt_content, vtt_path, txt_path = read_output_files()

        end_time = datetime.now()
        elapsed_time = end_time - start_time

        response_dict = {"status": "success", "total_time": str(elapsed_time)}

        if response_type == 'file':
            # Create zip file
            memory_file = zip_files(vtt_path, txt_path)
            
            # Create custom zip file name
            original_file_name, _ = os.path.splitext(file.filename)
            zip_file_name = f"{original_file_name}_transcribed.zip"

            return StreamingResponse(
                memory_file, 
                media_type="application/x-zip-compressed", 
                headers={"Content-Disposition": f"attachment; filename={zip_file_name}"}
            )
        else:
            response_dict.update({"vtt_content": vtt_content, "text_content": txt_content})

        return response_dict

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=int(API_PORT))
