import os
import subprocess
import logging
from zipfile import ZipFile
from io import BytesIO


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

#def convert_to_mp3(file_path):
#    temp_mp3_path = os.path.splitext(file_path)[0] + ".mp3"
#    subprocess.run(["ffmpeg", "-y", "-i", file_path, temp_mp3_path], check=True)
#    return temp_mp3_path

def convert_to_mp3(file_path):
    # Check if the file is already an MP3
    if os.path.splitext(file_path)[1].lower() != ".mp3":
        temp_mp3_path = os.path.splitext(file_path)[0] + ".mp3"
        try:
            logging.info(f"Converting {file_path} to {temp_mp3_path}")
            subprocess.run(["ffmpeg", "-y", "-i", file_path, temp_mp3_path], check=True)
            logging.info(f"Conversion to MP3 successful: {temp_mp3_path}")
        except subprocess.CalledProcessError as e:
            logging.error(f"ffmpeg conversion failed: {e}")
            raise
        return temp_mp3_path
    else:
        logging.info(f"File is already in MP3 format: {file_path}")
        return file_path

def read_output_files(base_name):
    output_dir = "./data/"
    vtt_path = f"{base_name}.vtt"
    txt_path = f"{base_name}.txt"
    json_path = f"{base_name}.json"
    srt_path = f"{base_name}.srt"
    
    with open(os.path.join(output_dir, vtt_path), "r") as vtt_file:
        vtt_content = vtt_file.read()

    with open(os.path.join(output_dir, txt_path), "r") as txt_file:
        txt_content = txt_file.read()
  
    with open(os.path.join(output_dir, json_path), "r") as json_file:
        json_content = json_file.read()
        
    with open(os.path.join(output_dir, srt_path), "r") as srt_file:
        srt_content = srt_file.read()

    return {
        "vtt_content": vtt_content,
        "txt_content": txt_content,
        "json_content": json_content,
        "srt_content": srt_content,
        "vtt_path": vtt_path,
        "txt_path": txt_path,
        "json_path": json_path,
        "srt_path": srt_path
    }
    
def zip_files(vtt_path, txt_path):
    memory_file = BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        zf.write(os.path.join("./data/", vtt_path), vtt_path)
        zf.write(os.path.join("./data/", txt_path), txt_path)
    memory_file.seek(0)
    return memory_file
  
  
