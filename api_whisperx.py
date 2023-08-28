import os
import subprocess
import requests
from fastapi import FastAPI, Depends, HTTPException, Query, Form, UploadFile
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
import sqlite3
import logging
import jwt

# Initialize FastAPI app and configure logging
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# SQLite database initialization
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute(
    "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)"
)
conn.commit()

# Secret key for JWT and master key for user creation
SECRET_KEY = "namastex_secret_key"
MASTER_KEY = "@Umasenha@2016"

# OAuth2 token location
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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
async def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_jwt_token(token)

@app.post("/token")
def get_token(username: str, password: str):
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and row[0] == password:
        return {"access_token": create_jwt_token({"sub": username}), "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/register_user")
def register_user(username: str, password: str, master_key: str = Query(...)):
    if master_key != MASTER_KEY:
        return JSONResponse(status_code=403, content={"detail": "Not authorized"})
    
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return {"detail": "User created successfully"}
    except sqlite3.IntegrityError:
        return JSONResponse(status_code=400, content={"detail": "Username already exists"})

@app.post("/whisperex-transcribe/")
async def process_video(
    file: UploadFile = None,
    min_speakers: int = Form(1),
    max_speakers: int = Form(2),
    current_user: dict = Depends(get_current_user)  # Add this line
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

        # Step 2: Convert the video to MP3 using ffmpeg
        temp_mp3_path = temp_video_path.replace(".mp4", ".mp3")
        subprocess.run(["ffmpeg", "-i", temp_video_path, temp_mp3_path], check=True)
        logging.info("Converted video to MP3.")

        # Step 3: Run the whisperx command on the MP3 file
        output_dir = "./data/namastex/"
        cmd = f"whisperx {temp_mp3_path} --model large-v2 --language pt --hf_token  --output_format all --output_dir {output_dir}  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers {min_speakers} --max_speakers {max_speakers}"
        subprocess.run(cmd.split())
        logging.info("Ran whisperx command.")

        # Step 4: Read the .vtt file
        vtt_path = [f for f in os.listdir(output_dir) if f.endswith(".vtt")][0]
        with open(os.path.join(output_dir, vtt_path), "r") as vtt_file:
            vtt_content = vtt_file.read()
        logging.info("Read .vtt file.")

        # Clean up temporary files
        os.remove(temp_video_path)
        os.remove(temp_mp3_path)
        logging.info("Cleaned up temporary files.")

        logging.info("Video processing completed successfully.")
        return {"status": "success", "vtt_content": "your_vtt_content", "summary": "your_summary"}

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11300)