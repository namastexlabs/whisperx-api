import subprocess
import os
import logging
from fastapi import FastAPI, UploadFile, HTTPException, Form
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()

@app.post("/whisperex-transcribe/")
async def process_video(
    file: UploadFile = None, min_speakers: int = Form(1), max_speakers: int = Form(2)
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
        cmd = f"whisperx {temp_mp3_path} --model large-v2 --language pt --hf_token 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 --output_format all --output_dir {output_dir}  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers {min_speakers} --max_speakers {max_speakers}"
        subprocess.run(cmd.split())
        logging.info("Ran whisperx command.")

        # Step 4: Read the .vtt file
        vtt_path = [f for f in os.listdir(output_dir) if f.endswith(".vtt")][0]
        with open(os.path.join(output_dir, vtt_path), "r") as vtt_file:
            vtt_content = vtt_file.read()
        logging.info("Read .vtt file.")

        # Send the VTT content to /generate-summary and get the result
        response = requests.post(
            "http://localhost:11301/generate-summary",
            data={
                "MEETING_TITLE": "",
                "MEETING_EXTRA_INFO": "",
                "SPEAKERS_INFO": "",
                "claude_model": "claude-2",
                "input_text": vtt_content,
                "output_file_name": "desired_output_file_name.txt",
            },
            timeout=6000,
        )
        logging.info("Sent request to /generate-summary.")

        if response.status_code == 200:
            summary = response.json().get("summary")
        else:
            summary = "Error generating summary."
        
        logging.info("Summary generation completed.")

        # Clean up temporary files
        os.remove(temp_video_path)
        os.remove(temp_mp3_path)
        logging.info("Cleaned up temporary files.")

        logging.info("Video processing completed successfully.")
        return {"status": "success", "vtt_content": vtt_content, "summary": summary}

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11300)
