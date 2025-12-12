"""GPU model singleton manager for WhisperX models."""

import threading
from typing import Any

import torch

# Import whisperx FIRST - the fork's compat.py applies all patches automatically
# (torch 2.6+, pyannote 4.x, torchaudio 2.9+)
import whisperx
from pyannote.audio import Pipeline

from whisperx_api.config import get_settings


class ModelManager:
    """Singleton manager for WhisperX GPU models.

    Ensures models are loaded only once and shared across requests.
    GPU model loading takes 30-60s, so we cache them.
    """

    _model: Any = None
    _align_models: dict[str, tuple[Any, Any]] = {}
    _diarize_model: Any = None
    _lock = threading.Lock()

    @classmethod
    def get_model(cls) -> Any:
        """Get or load the main WhisperX transcription model.

        Note: Uses "cuda" not "cuda:N" because faster_whisper/ctranslate2
        doesn't support device index in string. torch.cuda.set_device()
        is called at startup to select the correct GPU.
        """
        with cls._lock:
            if cls._model is None:
                settings = get_settings()
                print(
                    f"[whisperx-api] Loading WhisperX model: {settings.model} ({settings.compute_type})..."
                )
                cls._model = whisperx.load_model(
                    settings.model,
                    device="cuda",
                    compute_type=settings.compute_type,
                )
                print("[whisperx-api] WhisperX model loaded successfully")
            return cls._model

    @classmethod
    def get_align_model(cls, language: str) -> tuple[Any, Any]:
        """Get or load alignment model for a specific language."""
        with cls._lock:
            if language not in cls._align_models:
                print(f"[whisperx-api] Loading alignment model for language: {language}...")
                try:
                    model, metadata = whisperx.load_align_model(
                        language_code=language,
                        device="cuda",
                    )
                except ValueError as e:
                    raise RuntimeError(
                        f"Failed to load alignment model for '{language}'. "
                        f"This may be a network issue or corrupted cache.\n"
                        f"Try clearing cache: rm -rf ~/.cache/huggingface/hub/models--*{language}*\n"
                        f"Original error: {e}"
                    ) from e
                cls._align_models[language] = (model, metadata)
                print(f"[whisperx-api] Alignment model ({language}) loaded successfully")
            return cls._align_models[language]

    @classmethod
    def get_diarize_model(cls) -> Any:
        """Get or load speaker diarization model.

        Requires HuggingFace token and license acceptance:
        1. Accept license at https://hf.co/pyannote/speaker-diarization-community-1
        2. Set WHISPERX_HF_TOKEN in .env
        """
        with cls._lock:
            if cls._diarize_model is None:
                settings = get_settings()
                print(
                    "[whisperx-api] Loading diarization model: pyannote/speaker-diarization-community-1..."
                )

                pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-community-1",
                    token=settings.hf_token,
                )

                if pipeline is None:
                    raise RuntimeError(
                        "Failed to load diarization model. This model is gated on HuggingFace.\n"
                        "1. Accept license at https://hf.co/pyannote/speaker-diarization-community-1\n"
                        "2. Set WHISPERX_HF_TOKEN in .env with your HuggingFace token\n"
                        "   Get token at: https://hf.co/settings/tokens"
                    )

                cls._diarize_model = pipeline.to(torch.device(settings.device_str))
                print("[whisperx-api] Diarization model loaded successfully")
            return cls._diarize_model

    @classmethod
    def is_loaded(cls) -> bool:
        """Check if the main model is loaded."""
        return cls._model is not None

    @classmethod
    def preload(cls) -> None:
        """Preload the main transcription model."""
        print("[whisperx-api] Preloading models at startup...")
        cls.get_model()
        print("[whisperx-api] Startup preload complete - ready for requests")
