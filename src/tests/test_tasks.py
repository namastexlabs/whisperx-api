import os
import tempfile
from unittest.mock import patch
from api.tasks import transcribe_file

def test_transcribe_file_success():
    with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_video_file:
        # Create a temporary video file for testing
        temp_video_file.write(b"dummy video content")
        temp_video_file.flush()

        with patch("api.tasks.convert_to_mp3") as mock_convert_to_mp3, \
             patch("api.tasks.run_whisperx") as mock_run_whisperx, \
             patch("api.tasks.read_output_files") as mock_read_output_files:
            
            # Mock the behavior of the utility functions
            mock_convert_to_mp3.return_value = "temp_audio.mp3"
            mock_read_output_files.return_value = {
                "vtt_content": "dummy vtt content",
                "txt_content": "dummy txt content",
                "json_content": "dummy json content", 
                "srt_content": "dummy srt content",
                "vtt_path": "output.vtt",
                "txt_path": "output.txt",
                "json_path": "output.json",
                "srt_path": "output.srt"
            }

            result = transcribe_file(temp_video_file.name, "en", "base", 1, 2)

            assert result["status"] == "success"
            assert result["vtt_content"] == "dummy vtt content"
            assert result["txt_content"] == "dummy txt content"
            assert result["json_content"] == "dummy json content"
            assert result["srt_content"] == "dummy srt content"
            assert result["vtt_path"] == "output.vtt"
            assert result["txt_path"] == "output.txt" 
            assert result["json_path"] == "output.json"
            assert result["srt_path"] == "output.srt"

            mock_convert_to_mp3.assert_called_once_with(temp_video_file.name)
            mock_run_whisperx.assert_called_once_with("temp_audio.mp3", "en", "base", 1, 2)
            mock_read_output_files.assert_called_once()

def test_transcribe_file_exception():
    with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_video_file:
        temp_video_file.write(b"dummy video content") 
        temp_video_file.flush()

        with patch("api.tasks.convert_to_mp3") as mock_convert_to_mp3:
            mock_convert_to_mp3.side_effect = Exception("Test exception")

            try:
                transcribe_file(temp_video_file.name, "en", "base", 1, 2)
                assert False, "Expected an exception to be raised"
            except Exception as e:
                assert str(e) == "Test exception"