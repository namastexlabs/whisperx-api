import os
import tempfile
from unittest.mock import patch
from api.config import HF_TOKEN
from utils.transcription_utils import run_whisperx

def test_run_whisperx(mocker):
    # Test that the whisperx command is executed correctly
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        os.makedirs('./data')
        # Create a sample MP3 file
        with open('test.mp3', 'wb') as f:
            f.write(b'audio content')
        
        # Mock the subprocess.run function
        mock_run = mocker.patch('subprocess.run')
        
        run_whisperx('test.mp3', 'en', 'base', 1, 2)
        
        expected_cmd = f"whisperx test.mp3 --model base --language en --hf_token {HF_TOKEN} --output_format all --output_dir ./data/  --align_model WAV2VEC2_ASR_LARGE_LV60K_960H --diarize --min_speakers 1 --max_speakers 2"
        mock_run.assert_called_once_with(expected_cmd.split(), check=True)