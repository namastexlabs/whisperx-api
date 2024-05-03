import os
import subprocess

from src.api.config import HF_TOKEN


def run_whisperx(temp_mp3_path, lang, model, min_speakers, max_speakers):
    output_dir = "./data/"
    cmd = f"whisperx {temp_mp3_path} --model {model} --language {lang} --hf_token {HF_TOKEN} --output_format all --output_dir {output_dir}  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers {min_speakers} --max_speakers {max_speakers}"
    subprocess.run(cmd.split(), check=True)
