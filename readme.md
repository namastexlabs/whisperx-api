# Whisperx API Wrapper

## Overview

This is a FastAPI application that provides an endpoint for video/audio transcription using the `whisperx` command. The application supports multiple audio and video formats. It performs the transcription, alignment, and diarization of the uploaded media files.

## Features

- User Authentication with JWT
- Support for multiple audio and video formats
- Diarization support
- Customizable language and model settings

## Requirements

- whisperx
- Python 3.8+
- FastAPI
- ffmpeg
- SQLite
- pyjwt
- dotenv

Follow the instructions on how to install Whisperx [in the official repository](https://github.com/m-bain/whisperX#3-install-this-repo)
You can install these dependencies using the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in your root directory and add the following variables:

```env
SECRET_KEY=your_secret_key
MASTER_KEY=your_master_key
HUGGING_FACE_TOKEN=your_hugging_face_token
API_PORT=11300
```

## Database Setup

SQLite is used for storing user information. The database is created automatically when the application runs.

## Running the Application

Run the application using:

```bash
python api_whisperx.py
```

Replace `main` with the name of your Python file if it's not `main.py`.

## API Endpoints

### POST `/auth`

Authenticate a user and return a JWT token.

- `username`: The username of the user.
- `password`: The password of the user.

### POST `/create_user`

Create a new user.

- `username`: Desired username.
- `password`: Desired password.
- `master_key`: Master key for authorized user creation.

### POST `/whisperx-transcribe/`

Transcribe an uploaded audio or video file.

- `file`: The audio or video file to transcribe.
- `lang`: Language for transcription (default is "pt").
- `model`: Model to use for transcription (default is "large-v2").
- `min_speakers`: Minimum number of speakers for diarization (default is 1).
- `max_speakers`: Maximum number of speakers for diarization (default is 2).

## Logging

The application has built-in logging that informs about the steps being performed and any errors that occur.
