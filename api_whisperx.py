import os
import dotenv
dotenv.load_dotenv()
import subprocess
import requests
from fastapi import FastAPI, Depends, HTTPException, Query, Form, UploadFile
from fastapi.security import HTTPBearer, OAuth2PasswordBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import sqlite3
import logging
import jwt
from datetime import datetime

app = FastAPI(
    title="Whisperx API Wrapper",
    description="Upload a video or audio file and get a transcription in return, max file size is 100MB."
    summary="Simple API Wrapper for the Whisperx library",
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)
logging.basicConfig(level=logging.INFO)

def get_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)"
    )
    conn.commit()
    return conn, cursor

# Secret key for JWT and master key for user creation
SECRET_KEY = os.environ.get("SECRET_KEY", 'secret_key')
MASTER_KEY = os.environ.get("MASTER_KEY", 'master_key')
HF_TOKEN = os.environ.get("HUGGING_FACE_TOKEN")
API_PORT = os.environ.get("API_PORT", 11300)
API_HOST = os.environ.get("API_HOST", 'localhost')

# Create an instance of HTTPBearer
security = HTTPBearer()


# OAuth2 token location
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth", auto_error=False)

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
    
@app.get("/")
def read_root():
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
    return {"Date":  formatted_date, "info": "WhisperX API"}

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

@app.post("/whisperx-transcribe/")
async def generate_transcription(
    file: UploadFile = None,
    lang: str = Form("pt"),
    model: str = Form("large-v2"), 
    min_speakers: int = Form(1),
    max_speakers: int = Form(2),
    current_user: dict = Depends(get_current_user)  
):
    try:
        logging.info("Starting video processing.")
        # Create the directory if it doesn't exist
        if not os.path.exists('./temp'):
            os.makedirs('./temp')
        logging.info("Checked/created temp directory.")

        # Step 1: Save the uploaded file to a temporary location
        temp_video_path = f"./temp/{file.filename}"
        logging.info(f"Saving file to {temp_video_path}")
        with open(temp_video_path, "wb") as buffer:
            buffer.write(file.file.read())
        
        logging.info("File saved successfully.")

        # Step 2: Convert the video or audio to MP3 using ffmpeg
        file_extension = os.path.splitext(file.filename)[-1].lower()
        supported_formats = [".mp4", ".avi", ".mkv", ".flv", ".mov", ".wmv", ".webm", ".mp3", ".wav", ".flac"]

        if file_extension not in supported_formats:
            logging.error("Unsupported file format.")
            raise HTTPException(status_code=415, detail="Unsupported Media Type")

        temp_mp3_path = os.path.splitext(temp_video_path)[0] + ".mp3"

        # Skip conversion if the file is already an MP3
        if file_extension != ".mp3":
            subprocess.run(["ffmpeg", "-y", "-i", temp_video_path, temp_mp3_path], check=True)
            logging.info("Converted video/audio to MP3.")
        else:
            # If the file is already an MP3, simply rename it to the temp_mp3_path
            os.rename(temp_video_path, temp_mp3_path)
            logging.info("File is already in MP3 format.")
            
        # Step 3: Run the whisperx command on the MP3 file
        output_dir = "./data/"
        cmd = f"whisperx {temp_mp3_path} --model {model} --language {lang} --hf_token {HF_TOKEN} --output_format all --output_dir {output_dir}  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers {min_speakers} --max_speakers {max_speakers}"
        subprocess.run(cmd.split(), check=True)
        logging.info("Ran whisperx command.")
        # Check if the MP3 file still exists
        if os.path.exists(temp_mp3_path):
            logging.info(f"The MP3 file {temp_mp3_path} exists.")
        else:
            logging.warning(f"The MP3 file {temp_mp3_path} does not exist.")


        # Step 4: Read the .vtt file
        vtt_path = [f for f in os.listdir(output_dir) if f.endswith(".vtt")][0]
        with open(os.path.join(output_dir, vtt_path), "r") as txt_file:
            vtt_content = txt_file.read()
        logging.info("Read .vtt file.")
        
         # Step 5: Read the .TXT file
        txt_path = [f for f in os.listdir(output_dir) if f.endswith(".txt")][0]
        with open(os.path.join(output_dir, txt_path), "r") as txt_file:
            txt_content = txt_file.read()

       # Clean up temporary files
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if os.path.exists(temp_mp3_path):
            os.remove(temp_mp3_path)
        logging.info("Cleaned up temporary files.")

        logging.info("Video processing completed successfully.")
        return {"status": "success", "vtt_content":vtt_content , "text_content": txt_content}

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=int(API_PORT))