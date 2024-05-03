import os
import tempfile
from unittest.mock import MagicMock, patch
from src.utils.file_utils import (
    create_directories,
    save_uploaded_file,
    convert_to_mp3,
    read_output_files,
    zip_files,
)


def test_create_directories():
    # Test that the directories are created if they don't exist
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        create_directories()
        assert os.path.exists("./temp")
        assert os.path.exists("./data")


def test_save_uploaded_file():
    # Test that the uploaded file is saved correctly
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        os.makedirs("./temp")
        file_mock = MagicMock()
        file_mock.filename = "test.mp4"
        file_mock.file.read.return_value = b"file content"
        temp_video_path = save_uploaded_file(file_mock)
        assert os.path.exists(temp_video_path)
        with open(temp_video_path, "rb") as f:
            assert f.read() == b"file content"


def test_convert_to_mp3(mocker):
    # Test that the video file is converted to MP3 correctly
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        # Create a sample video file path
        video_file_path = "test.mp4"

        # Create a sample video file
        with open(video_file_path, "wb") as f:
            f.write(b"sample video content")

        # Mock the subprocess.run function
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        temp_mp3_path = convert_to_mp3(video_file_path)

        assert temp_mp3_path.endswith(".mp3")

        # Check if ffmpeg command was called with the correct arguments
        mock_run.assert_called_once_with(
            ["ffmpeg", "-y", "-i", video_file_path, temp_mp3_path], check=True
        )


def test_read_output_files():
    # Test that the output files are read correctly
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        os.makedirs("./data")
        # Create sample output files
        with open("./data/test.vtt", "w") as f:
            f.write("vtt content")
        with open("./data/test.txt", "w") as f:
            f.write("txt content")
        with open("./data/test.json", "w") as f:
            f.write("json content")
        with open("./data/test.srt", "w") as f:
            f.write("srt content")
        output_files = read_output_files("test")
        assert output_files["vtt_content"] == "vtt content"
        assert output_files["txt_content"] == "txt content"
        assert output_files["json_content"] == "json content"
        assert output_files["srt_content"] == "srt content"
        assert output_files["vtt_path"] == "test.vtt"
        assert output_files["txt_path"] == "test.txt"
        assert output_files["json_path"] == "test.json"
        assert output_files["srt_path"] == "test.srt"


def test_zip_files():
    # Test that the files are zipped correctly
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        os.makedirs("./data")
        # Create sample files
        with open("./data/test.vtt", "w") as f:
            f.write("vtt content")
        with open("./data/test.txt", "w") as f:
            f.write("txt content")
        memory_file = zip_files("test.vtt", "test.txt")
        assert memory_file.getvalue().startswith(
            b"PK"
        )  # Check if the file starts with a ZIP file signature
