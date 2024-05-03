import logging
import os
from src.api.config import BROKER_URL
from celery import Celery
from src.utils.file_utils import convert_to_mp3, read_output_files
from src.utils.transcription_utils import run_whisperx

celery_app = Celery(
    "whisperx-tasks", backend="db+sqlite:///celery.db", broker=BROKER_URL
)


@celery_app.task(name="transcribe_file")
def transcribe_file(temp_video_path, lang, model, min_speakers, max_speakers):
    try:
        temp_mp3_path = convert_to_mp3(temp_video_path)
        base_name = os.path.splitext(os.path.basename(temp_mp3_path))[0]
        run_whisperx(temp_mp3_path, lang, model, min_speakers, max_speakers)
        output_files = read_output_files(base_name)
        result = {
            "status": "success",
            "vtt_content": output_files["vtt_content"],
            "txt_content": output_files["txt_content"],
            "json_content": output_files["json_content"],
            "srt_content": output_files["srt_content"],
            "vtt_path": output_files["vtt_path"],
            "txt_path": output_files["txt_path"],
            "json_path": output_files["json_path"],
            "srt_path": output_files["srt_path"],
        }
        return result

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise e
