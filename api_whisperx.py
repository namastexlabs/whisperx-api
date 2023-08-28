from fastapi import FastAPI, UploadFile, HTTPException, Form
import subprocess
import os
import requests

app = FastAPI()


@app.post("/whisperex-transcribe/")
async def process_video(
    file: UploadFile = None, min_speakers: int = Form(1), max_speakers: int = Form(2)
):
    try:
        # Step 1: Save the uploaded file to a temporary location
        temp_video_path = f"./temp/{file.filename}"
        with open(temp_video_path, "wb") as buffer:
            buffer.write(file.file.read())

        # Step 2: Convert the video to MP3 using ffmpeg
        temp_mp3_path = temp_video_path.replace(".mp4", ".mp3")
        subprocess.run(["ffmpeg", "-i", temp_video_path, temp_mp3_path])

        # Step 3: Run the whisperx command on the MP3 file
        output_dir = "./data/namastex/"

        cmd = f"whisperx {temp_mp3_path} --model large-v2 --language pt --hf_token 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 --output_format all --output_dir {output_dir}  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers {min_speakers} --max_speakers {max_speakers}"
        subprocess.run(cmd.split())

        # Step 4: Read the .vtt file
        vtt_path = [f for f in os.listdir(output_dir) if f.endswith(".vtt")][0]
        with open(os.path.join(output_dir, vtt_path), "r") as vtt_file:
            vtt_content = vtt_file.read()

        # Send the VTT content to /generate-summary and get the result
        print(vtt_content)
        print("Sending request to /generate-summary")
        response = requests.post(
            "http://localhost:11301/generate-summary",
            data={
                "MEETING_TITLE": "",  # Replace with actual title if available
                "MEETING_EXTRA_INFO": "",  # Replace with actual extra info if available
                "SPEAKERS_INFO": "",  # Replace with actual speakers info if available
                "claude_model": "claude-2",  # Replace with the desired model
                "input_text": vtt_content,
                "output_file_name": "desired_output_file_name.txt",  # Replace with the desired file name
            },
            timeout=6000,
        )

        if response.status_code == 200:
            summary = response.json().get("summary")
        else:
            summary = "Error generating summary."

        # Clean up temporary files
        os.remove(temp_video_path)
        os.remove(temp_mp3_path)

        return {"status": "success", "vtt_content": vtt_content, "summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=11300)
