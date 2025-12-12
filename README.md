<h1 align="center">WhisperX API</h1>

<p align="center">
  <strong>GPU-powered transcription API in one command</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/whisperx-api/">
    <img src="https://img.shields.io/pypi/v/whisperx-api?style=flat-square&color=00D9FF" alt="PyPI">
  </a>
  <a href="https://github.com/namastexlabs/whisperx-api/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/namastexlabs/whisperx-api/ci.yml?style=flat-square" alt="CI">
  </a>
  <img src="https://img.shields.io/badge/python-3.12-blue?style=flat-square" alt="Python 3.12">
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
  </a>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-configuration">Config</a> •
  <a href="#-development">Development</a>
</p>

---

Turn any audio into text with speaker labels. No cloud. No limits. Just run:

```bash
uvx whisperx-api
```

WhisperX API wraps [WhisperX](https://github.com/m-bain/whisperX) in a REST API with speaker diarization, word-level timestamps, and multiple export formats. Self-hosted alternative to AssemblyAI, Deepgram, and Rev.ai.

## Features

- **Speaker Diarization** - Identify who said what with pyannote
- **Word-Level Timestamps** - Precise alignment for every word
- **Multiple Export Formats** - SRT, WebVTT, TXT, JSON
- **Webhook Callbacks** - Get notified when transcription completes
- **GPU Model Caching** - Fast subsequent transcriptions
- **Background Processing** - Non-blocking async jobs
- **Progress Tracking** - Poll for real-time status

## Quick Start

### Prerequisites

- **NVIDIA GPU** with 6GB+ VRAM (or CPU mode for testing)
- **CUDA 12.x** drivers installed

### Option A: One-Liner Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/namastexlabs/whisperx-api/main/get-whisperx.sh | bash
```

This installs Python 3.12, uv, checks CUDA, and sets up whisperx-api.

### Option B: Direct Run (if dependencies met)

```bash
uvx whisperx-api
```

### Option C: pip install

```bash
pip install whisperx-api
whisperx-api
```

The API starts at `http://localhost:8880`. Swagger docs at `/docs`.

### First Transcription

```bash
# Default API key is "namastex888" - works out of the box
curl -X POST http://localhost:8880/v1/transcript \
  -H "Authorization: namastex888" \
  -F "file=@audio.mp3"

# Check status (replace {id} with returned transcript ID)
curl http://localhost:8880/v1/transcript/{id} \
  -H "Authorization: namastex888"
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/transcript` | Submit transcription job |
| `GET` | `/v1/transcript/{id}` | Get transcript status/result |
| `GET` | `/v1/transcript/{id}/srt` | Export as SRT subtitles |
| `GET` | `/v1/transcript/{id}/vtt` | Export as WebVTT |
| `GET` | `/v1/transcript/{id}/txt` | Export as plain text |
| `GET` | `/v1/transcript/{id}/json` | Export as JSON |
| `DELETE` | `/v1/transcript/{id}` | Delete transcript |
| `GET` | `/health` | Health check (no auth) |

### Submit Transcription

**File upload:**
```bash
curl -X POST http://localhost:8880/v1/transcript \
  -H "Authorization: namastex888" \
  -F "file=@audio.mp3"
```

**URL download:**
```bash
curl -X POST http://localhost:8880/v1/transcript \
  -H "Authorization: namastex888" \
  -F "audio_url=https://example.com/audio.mp3"
```

**With speaker diarization:**
```bash
curl -X POST http://localhost:8880/v1/transcript \
  -H "Authorization: namastex888" \
  -F "file=@audio.mp3" \
  -F "speaker_labels=true" \
  -F "speakers_expected=2"
```

### Response Format

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "text": "Hello world, this is a transcription.",
  "words": [
    {"text": "Hello", "start": 0, "end": 500, "confidence": 0.98, "speaker": "A"}
  ],
  "utterances": [
    {"speaker": "A", "text": "Hello world...", "start": 0, "end": 3000}
  ],
  "language_code": "en"
}
```

**Status values:** `queued` → `processing` → `completed` (or `error`)

## Configuration

All settings via environment variables with `WHISPERX_` prefix. Everything has sensible defaults - no `.env` file needed for local use.

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPERX_API_KEY` | `namastex888` | API authentication key |
| `WHISPERX_HOST` | `0.0.0.0` | Server bind address |
| `WHISPERX_PORT` | `8880` | Server port |
| `WHISPERX_MODEL` | `large-v3-turbo` | WhisperX model |
| `WHISPERX_DATA_DIR` | `./data` | SQLite database location |
| `WHISPERX_HF_TOKEN` | - | HuggingFace token (for diarization) |
| `WHISPERX_DEVICE` | `0` | GPU device index |

### Speaker Diarization Setup

To enable `speaker_labels=true`:

1. **Accept license** at [pyannote/speaker-diarization](https://hf.co/pyannote/speaker-diarization-community-1)
2. **Get token** at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
3. **Add to config:**
   ```bash
   echo "WHISPERX_HF_TOKEN=hf_xxx" >> ~/.config/whisperx-api/.env
   ```

## Troubleshooting

**CUDA not available:**
```bash
# Check NVIDIA driver
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

**Out of VRAM:**
- Use smaller model: `WHISPERX_MODEL=medium`
- Reduce batch size: `WHISPERX_BATCH_SIZE=8`

**Diarization fails:**
- Verify HF token: `echo $WHISPERX_HF_TOKEN`
- Accept license at HuggingFace (link above)

---

## Built On

This project wraps the incredible [WhisperX](https://github.com/m-bain/whisperX) by [@m-bain](https://github.com/m-bain) - fast automatic speech recognition with word-level timestamps and speaker diarization.

---

<details>
<summary><h2>Development</h2></summary>

### Setup

```bash
git clone https://github.com/namastexlabs/whisperx-api.git
cd whisperx-api
uv sync
```

### Run Tests

```bash
uv run pytest tests/ -v
```

### Code Quality

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

### Project Structure

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
│   └── main.py            # CLI entry point
├── tests/                 # Test suite
├── get-whisperx.sh        # One-liner installer
└── pyproject.toml         # Project config
```

### CI/CD

- **CI:** Runs on every push (lint, typecheck, test)

### Performance Notes

- **First request:** ~60-90s (model loading)
- **Subsequent:** ~same as audio duration
- **VRAM usage:** ~5-6GB for large-v3-turbo

</details>

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/namastexlabs">Namastex Labs</a>
</p>

<p align="center">
  <a href="https://github.com/namastexlabs/whisperx-api">
    <img src="https://img.shields.io/github/stars/namastexlabs/whisperx-api?style=social" alt="Star us on GitHub">
  </a>
</p>
