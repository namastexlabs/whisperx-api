# WhisperX API with Asynchronous Transcription

A FastAPI-based web API for asynchronous audio and video transcription using [WhisperX](https://github.com/m-bain/whisperX).

## Overview

This project provides an API to upload media files and receive transcriptions, including alignment and speaker diarization. It leverages Celery task queues and RabbitMQ to handle transcription jobs asynchronously, allowing the API to remain responsive while processing resource-intensive tasks in the background.

## Features

- Asynchronous transcription processing with Celery
- RabbitMQ message broker integration
- Support for multiple audio and video formats
- Speaker diarization support
- Customizable language and model settings
- Built-in logging
- Job status tracking via API

## Requirements

- Python 3.8+
- [WhisperX](https://github.com/m-bain/whisperX)
- FastAPI
- ffmpeg
- SQLite (for internal use, not user management)
- python-dotenv
- Celery
- RabbitMQ server

### Installing dependencies

Follow the WhisperX installation instructions: [WhisperX repo](https://github.com/m-bain/whisperX#3-install-this-repo)

Then install Python dependencies:

```bash
pip install -r requirements.txt
```

### RabbitMQ installation

RabbitMQ is required as the message broker for Celery. On Ubuntu, install it via:

```bash
sudo apt-get update
sudo apt-get install rabbitmq-server -y
sudo systemctl enable --now rabbitmq-server
```

Ensure RabbitMQ is running before starting the application.

## Environment Variables

Create a `.env` file in your project root with:

```env
HUGGING_FACE_TOKEN=your_hugging_face_token
API_PORT=11300
```

## Running the Application

### 1. Start the FastAPI server

```bash
python start.py
```

This launches the API server (default on port 11300).


## API Endpoints

### POST `/jobs`

Submit a new transcription job with an uploaded media file.

### GET `/jobs`

List all submitted transcription jobs.

### GET `/jobs/{task_id}`

Get the status and result of a specific transcription job.

## Logging

The application logs key events and errors during API requests and background task processing.

## Summary

This project provides a scalable, asynchronous API for audio/video transcription using WhisperX, with support for speaker diarization and job status tracking.
