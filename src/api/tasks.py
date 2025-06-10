import logging
import os
from src.api.config import BROKER_URL
from celery import Celery
from src.utils.file_utils import convert_to_mp3, read_output_files
from src.utils.transcription_utils import run_whisperx
from celery.signals import setup_logging

celery_app = Celery(
    "whisperx-tasks", backend="db+sqlite:///celery.db", broker=BROKER_URL
)

@setup_logging.connect
def configure_celery_logging(**kwargs):
    # Suppress task success logging
    logging.getLogger("celery.app.trace").setLevel(logging.WARNING)

@celery_app.task(name="transcribe_file")
def transcribe_file(temp_video_path, lang, model, min_speakers, max_speakers, prompt):
    try:
        logging.info(f"Starting transcription task with video path: {temp_video_path}")

        if not os.path.exists(temp_video_path):
            logging.error(f"File not found: {temp_video_path}")
            raise FileNotFoundError(f"File not found: {temp_video_path}")

        logging.info("Converting video to mp3...")
        temp_mp3_path = convert_to_mp3(temp_video_path)
        logging.info(f"Conversion complete. MP3 path: {temp_mp3_path}")

        base_name = os.path.splitext(os.path.basename(temp_mp3_path))[0]

        # Ensure base_name is logged and working directory is correct
        logging.info(f"Base name for transcription: {base_name}")

        run_whisperx(temp_mp3_path, lang, model, min_speakers, max_speakers, prompt)
        logging.info(f"WhisperX transcription completed for base: {base_name}")

        output_files = read_output_files(base_name)
        logging.info("Reading output files completed")

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
        #logging.info(f"Task result: {result}")
        return result

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise e
