# WhisperX API

Local WhisperX transcription service with AssemblyAI-compatible API.

## Features

- **AssemblyAI-compatible API** - Drop-in replacement for AssemblyAI transcription
- **Speaker diarization** - Identify and label multiple speakers
- **Word-level timestamps** - Precise alignment for each word
- **Multiple export formats** - SRT, WebVTT, TXT, JSON
- **Webhook notifications** - Async result delivery
- **GPU model caching** - Fast subsequent transcriptions after initial load
- **Background processing** - Non-blocking async transcription
- **Progress tracking** - Poll for real-time status updates

## Requirements

- **Python 3.12** (exact version required)
- **NVIDIA GPU** with CUDA 12.6 support
- **8-16GB VRAM** (for large-v3-turbo model)
- **ffmpeg** (system-installed or bundled automatically)
- **HuggingFace token** (only for speaker diarization)

## Quick Start

### 1. Install with uv (recommended)

```bash
git clone https://github.com/namastexlabs/whisperx-api.git
cd whisperx-api
uv sync
```

### 2. Configure environment

```bash
cp .env-example .env
# Edit .env and set WHISPERX_API_KEY
```

### 3. Start the server

```bash
whisperx-api
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

## Configuration

All configuration is via environment variables with `WHISPERX_` prefix:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WHISPERX_API_KEY` | **Yes** | - | API authentication key |
| `WHISPERX_HOST` | No | `0.0.0.0` | Server bind address |
| `WHISPERX_PORT` | No | `8000` | Server port |
| `WHISPERX_MODEL` | No | `large-v3-turbo` | WhisperX model size |
| `WHISPERX_COMPUTE_TYPE` | No | `float16` | Model precision (`float16` or `float32`) |
| `WHISPERX_BATCH_SIZE` | No | `16` | Transcription batch size |
| `WHISPERX_DEVICE` | No | `0` | GPU device index (for multi-GPU) |
| `WHISPERX_LANGUAGE` | No | auto-detect | Default language code (e.g., `en`, `pt`, `es`) |
| `WHISPERX_HF_TOKEN` | For diarization | - | HuggingFace access token |
| `WHISPERX_DATA_DIR` | No | `./data` | Data storage directory |
| `WHISPERX_MAX_UPLOAD_SIZE_MB` | No | `2048` | Max file upload size (2GB) |
| `WHISPERX_PRELOAD_LANGUAGES` | No | - | Comma-separated languages to preload |

## API Reference

### Authentication

All `/v1/*` endpoints require an API key via the `Authorization` header:

```bash
Authorization: Bearer your-api-key
# or simply:
Authorization: your-api-key
```

### Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | No | Health check |
| `GET` | `/ready` | No | GPU readiness check |
| `POST` | `/v1/transcript` | Yes | Submit transcription job |
| `GET` | `/v1/transcript` | Yes | List all transcripts |
| `GET` | `/v1/transcript/{id}` | Yes | Get transcript status/result |
| `GET` | `/v1/transcript/{id}/srt` | Yes | Export as SRT subtitles |
| `GET` | `/v1/transcript/{id}/vtt` | Yes | Export as WebVTT subtitles |
| `GET` | `/v1/transcript/{id}/txt` | Yes | Export as plain text |
| `GET` | `/v1/transcript/{id}/json` | Yes | Export as JSON |
| `DELETE` | `/v1/transcript/{id}` | Yes | Delete transcript |

### Submit Transcription

**File upload:**

```bash
curl -X POST http://localhost:8000/v1/transcript \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@audio.mp3"
```

**URL download:**

```bash
curl -X POST http://localhost:8000/v1/transcript \
  -H "Authorization: Bearer your-api-key" \
  -F "audio_url=https://example.com/audio.mp3"
```

**With options:**

```bash
curl -X POST http://localhost:8000/v1/transcript \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@audio.mp3" \
  -F "language_code=en" \
  -F "speaker_labels=true"
```

### Poll for Status

```bash
curl http://localhost:8000/v1/transcript/{id} \
  -H "Authorization: Bearer your-api-key"
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 1.0,
  "text": "Hello world, this is a transcription.",
  "words": [
    {"text": "Hello", "start": 0, "end": 500, "confidence": 0.98, "speaker": "A"},
    {"text": "world", "start": 500, "end": 1000, "confidence": 0.96, "speaker": "A"}
  ],
  "utterances": [
    {
      "speaker": "A",
      "text": "Hello world, this is a transcription.",
      "start": 0,
      "end": 3000,
      "confidence": 0.97
    }
  ],
  "confidence": 0.97,
  "audio_duration": 3000,
  "language_code": "en"
}
```

**Status values:**
- `queued` - Job submitted, waiting to process
- `processing` - Transcription in progress
- `completed` - Done, results available
- `error` - Failed, check `error` field

## Speaker Diarization

To enable speaker identification:

### 1. Accept the model license

Visit [pyannote/speaker-diarization-community-1](https://hf.co/pyannote/speaker-diarization-community-1) and accept the license.

### 2. Get a HuggingFace token

Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

### 3. Configure the token

```bash
# In .env
WHISPERX_HF_TOKEN=hf_your_token_here
```

### 4. Use speaker_labels

```bash
curl -X POST http://localhost:8000/v1/transcript \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@audio.mp3" \
  -F "speaker_labels=true" \
  -F "speakers_expected=2"
```

## Export Formats

### SRT Subtitles

```bash
curl http://localhost:8000/v1/transcript/{id}/srt \
  -H "Authorization: Bearer your-api-key"
```

```srt
1
00:00:00,000 --> 00:00:03,000
Hello world, this is a transcription.

2
00:00:03,000 --> 00:00:06,000
And this is the second sentence.
```

### WebVTT Subtitles

```bash
curl http://localhost:8000/v1/transcript/{id}/vtt \
  -H "Authorization: Bearer your-api-key"
```

```vtt
WEBVTT

00:00:00.000 --> 00:00:03.000
Hello world, this is a transcription.

00:00:03.000 --> 00:00:06.000
And this is the second sentence.
```

## Advanced Options

The POST `/v1/transcript` endpoint accepts these optional parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language_code` | string | auto | Language code (e.g., `en`, `pt`, `es`) |
| `speaker_labels` | bool | false | Enable speaker diarization |
| `speakers_expected` | int | - | Expected number of speakers |
| `min_speakers` | int | - | Minimum speakers |
| `max_speakers` | int | - | Maximum speakers |
| `task` | string | transcribe | `transcribe` or `translate` (to English) |
| `temperature` | float | 0.0 | Sampling temperature (0.0-1.0) |
| `beam_size` | int | 5 | Beam search size |
| `initial_prompt` | string | - | Prompt for context |
| `hotwords` | string | - | Comma-separated words to boost |
| `word_timestamps` | bool | true | Include word-level timestamps |
| `webhook_url` | string | - | URL for completion callback |
| `webhook_auth_header` | string | - | Auth header for webhook |

## Development

### Run tests

```bash
uv run pytest tests/ -v
```

### Code quality

```bash
uv run ruff check .
uv run mypy src/
```

### Project structure

```
whisperx-api/
├── src/whisperx_api/
│   ├── server.py          # FastAPI application
│   ├── transcriber.py     # WhisperX pipeline
│   ├── model_manager.py   # GPU model caching
│   ├── database.py        # SQLite persistence
│   ├── config.py          # Settings management
│   ├── auth.py            # API authentication
│   ├── models.py          # Pydantic schemas
│   ├── deps.py            # Dependency checks
│   └── main.py            # Entry point
├── tests/                 # Test suite
├── pyproject.toml         # Project config
└── .env-example           # Config template
```

## Performance

- **First request:** ~60-90 seconds (model loading)
- **Subsequent requests:** ~same duration as audio
- **GPU memory:** ~8-12GB for large-v3-turbo
- **Concurrent requests:** Queued sequentially per GPU

## Troubleshooting

### CUDA not available

```bash
# Check CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Install PyTorch with CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

### Model loading fails

```bash
# Clear HuggingFace cache
rm -rf ~/.cache/huggingface/hub/models--*

# Check GPU memory
nvidia-smi
```

### Diarization fails

1. Verify HF token is set: `echo $WHISPERX_HF_TOKEN`
2. Verify license accepted at [huggingface.co](https://hf.co/pyannote/speaker-diarization-community-1)
3. Check token has read access

## License

MIT License - see [LICENSE](LICENSE) file.
