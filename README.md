<h1 align="center">MurmurAI</h1>

<p align="center">
  <img src=".github/images/murmur-200.png" alt="MurmurAI Logo" width="200">
</p>

<p align="center">
  <strong>🎙️ Drop-in replacement for paid transcription APIs. Self-hosted, GPU-powered, speaker diarization. Free forever.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/murmurai/">
    <img src="https://img.shields.io/pypi/v/murmurai?style=flat-square&color=00D9FF" alt="PyPI">
  </a>
  <a href="https://github.com/namastexlabs/murmurai/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/namastexlabs/murmurai/ci.yml?style=flat-square" alt="CI">
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
  <a href="#-security">Security</a> •
  <a href="#-development">Development</a>
</p>

---

Turn any audio into text with speaker labels. No cloud. No limits. Just run:

```bash
uvx murmurai
```

MurmurAI wraps [murmurai-core](https://pypi.org/project/murmurai-core/) (our WhisperX fork) in a REST API with speaker diarization, word-level timestamps, and multiple export formats. Self-hosted alternative to AssemblyAI, Deepgram, and Rev.ai.

## Features

- **Speaker Diarization** - Identify who said what with pyannote
- **Word-Level Timestamps** - Precise alignment for every word
- **Multiple Export Formats** - SRT, WebVTT, TXT, JSON
- **Webhook Callbacks** - Get notified when transcription completes
- **GPU Model Caching** - Fast subsequent transcriptions
- **Background Processing** - Non-blocking async jobs
- **Progress Tracking** - Poll for real-time status

## 🔮 What's Next

We're a research lab. Stars tell us what the community wants — help us prioritize!

<p align="center">
  <a href="https://github.com/namastexlabs/murmurai">
    <img src="https://img.shields.io/github/stars/namastexlabs/murmurai?style=for-the-badge&logo=github&label=Star%20to%20Unlock&color=f59e0b" alt="Star to unlock">
  </a>
</p>

<p align="center">
  🔒 <b>250 ⭐</b> Desktop App &nbsp;&nbsp;│&nbsp;&nbsp;
  🔒 <b>500 ⭐</b> MCP Server &nbsp;&nbsp;│&nbsp;&nbsp;
  🔒 <b>750 ⭐</b> Native Apple Silicon (MLX) &nbsp;&nbsp;│&nbsp;&nbsp;
  🔒 <b>1000 ⭐</b> Real-time Streaming
</p>

## Quick Start

### Prerequisites

- **NVIDIA GPU** with 6GB+ VRAM (or CPU mode for testing)
- **CUDA 12.x** drivers installed

### Option A: One-Liner Install (Recommended)

```bash
curl -fsSL https://install.namastex.ai/get-murmurai.sh | bash
```

This installs Python 3.12, uv, checks CUDA, and sets up murmurai.

### Option B: Direct Run (if dependencies met)

```bash
uvx murmurai
```

### Option C: pip install

```bash
pip install murmurai
murmurai
```

### Option D: Docker (GPU required)

```bash
# Clone and run with docker compose
git clone https://github.com/namastexlabs/murmurai.git
cd murmurai
docker compose up
```

Requires NVIDIA Container Toolkit. Set `MURMURAI_API_KEY` in environment for production.

### Windows Install

Windows requires PyTorch with CUDA from PyTorch's index (PyPI only has CPU wheels for Windows).

```powershell
# One command (auto-detects CUDA):
uv pip install murmurai --torch-backend=auto

# Or manually:
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install murmurai
```

If you see "PyTorch is CPU-only", reinstall with `--torch-backend=auto` or use the manual method above.

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

All settings via environment variables with `MURMURAI_` prefix. Everything has sensible defaults - no `.env` file needed for local use.

| Variable | Default | Description |
|----------|---------|-------------|
| `MURMURAI_API_KEY` | `namastex888` | API authentication key |
| `MURMURAI_HOST` | `0.0.0.0` | Server bind address |
| `MURMURAI_PORT` | `8880` | Server port |
| `MURMURAI_MODEL` | `large-v3-turbo` | Whisper model |
| `MURMURAI_DATA_DIR` | `./data` | SQLite database location |
| `MURMURAI_HF_TOKEN` | - | HuggingFace token (for diarization) |
| `MURMURAI_DEVICE` | `0` | GPU device index |
| `MURMURAI_LOG_FORMAT` | `text` | Logging format (`text` or `json`) |
| `MURMURAI_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Speaker Diarization Setup

To enable `speaker_labels=true`:

1. **Accept license** at [pyannote/speaker-diarization](https://hf.co/pyannote/speaker-diarization-community-1)
2. **Get token** at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
3. **Add to config:**
   ```bash
   echo "MURMURAI_HF_TOKEN=hf_xxx" >> ~/.config/murmurai/.env
   ```

## Security

### Default API Key Warning

MurmurAI ships with a default API key (`namastex888`) for zero-config local use. **This key is publicly known.**

**For any network-exposed deployment, set a secure key:**

```bash
# Generate a secure random key
export MURMURAI_API_KEY=$(openssl rand -hex 32)

# Or add to your .env file
echo "MURMURAI_API_KEY=$(openssl rand -hex 32)" >> .env
```

The server will display a security warning at startup if using the default key.

### Network Exposure

- **Local-only (default):** Safe to use default key for `localhost` testing
- **LAN/Docker:** Change the API key before exposing to your network
- **Internet:** **Always** use a strong API key + consider a reverse proxy with HTTPS

### SSRF Protection

The API validates all `audio_url` parameters to prevent Server-Side Request Forgery:

- Blocks internal IPs (127.0.0.1, 10.x.x.x, 192.168.x.x, etc.)
- Blocks cloud metadata endpoints (169.254.169.254)
- Only allows HTTP/HTTPS schemes
- Resolves DNS and validates the resolved IP

## Troubleshooting

**CUDA not available:**
```bash
# Check NVIDIA driver
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

**Out of VRAM:**
- Use smaller model: `MURMURAI_MODEL=medium`
- Reduce batch size: `MURMURAI_BATCH_SIZE=8`

**Diarization fails:**
- Verify HF token: `echo $MURMURAI_HF_TOKEN`
- Accept license at HuggingFace (link above)

---

## Built On

This project uses [murmurai-core](https://pypi.org/project/murmurai-core/) - our maintained fork of [WhisperX](https://github.com/m-bain/whisperX) with modern dependency support (PyTorch 2.6+, Pyannote 4.x, Python 3.10-3.13).

---

<details>
<summary><h2>Development</h2></summary>

### Setup

```bash
git clone https://github.com/namastexlabs/murmurai.git
cd murmurai
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
murmurai/
├── src/murmurai/
│   ├── server.py          # FastAPI application
│   ├── transcriber.py     # Transcription pipeline
│   ├── model_manager.py   # GPU model caching
│   ├── database.py        # SQLite persistence
│   ├── config.py          # Settings management
│   ├── auth.py            # API authentication
│   ├── models.py          # Pydantic schemas
│   ├── deps.py            # Dependency checks
│   └── main.py            # CLI entry point
├── tests/                 # Test suite
├── get-murmurai.sh        # One-liner installer
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
  <a href="https://github.com/namastexlabs/murmurai">
    <img src="https://img.shields.io/github/stars/namastexlabs/murmurai?style=social" alt="Star us on GitHub">
  </a>
</p>
