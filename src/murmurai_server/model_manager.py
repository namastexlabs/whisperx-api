"""GPU model singleton manager for transcription models."""

import threading
from typing import Any

# Import murmurai FIRST - the fork's compat.py applies all patches automatically
# (torch 2.6+, pyannote 4.x, torchaudio 2.9+)
import murmurai as murmurai_core  # type: ignore[import-untyped]
import torch
from pyannote.audio import Pipeline

from murmurai_server.config import get_settings
from murmurai_server.logging import get_logger


class ModelManager:
    """Singleton manager for GPU models.

    Ensures models are loaded only once and shared across requests.
    GPU model loading takes 30-60s, so we cache them.
    """

    _model: Any = None
    _align_models: dict[str, tuple[Any, Any]] = {}
    _diarize_models: dict[str, Any] = {}  # Cache by model name
    _lock = threading.Lock()

    @classmethod
    def get_model(cls) -> Any:
        """Get or load the main transcription model.

        Note: Uses "cuda" not "cuda:N" because faster_whisper/ctranslate2
        doesn't support device index in string. torch.cuda.set_device()
        is called at startup to select the correct GPU.
        """
        with cls._lock:
            if cls._model is None:
                settings = get_settings()
                logger = get_logger()
                logger.info(f"Loading model: {settings.model} ({settings.compute_type})...")
                cls._model = murmurai_core.load_model(
                    settings.model,
                    device="cuda",
                    compute_type=settings.compute_type,
                )
                logger.info("Model loaded successfully")
            return cls._model

    @classmethod
    def get_align_model(cls, language: str) -> tuple[Any, Any]:
        """Get or load alignment model for a specific language."""
        with cls._lock:
            if language not in cls._align_models:
                logger = get_logger()
                logger.info(f"Loading alignment model for language: {language}...")
                try:
                    model, metadata = murmurai_core.load_align_model(
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
                logger.info(f"Alignment model ({language}) loaded successfully")
            return cls._align_models[language]

    @classmethod
    def get_diarize_model(cls, model_name: str = "pyannote/speaker-diarization-3.1") -> Any:
        """Get or load speaker diarization model.

        Args:
            model_name: HuggingFace model ID. Options:
                - pyannote/speaker-diarization-3.1 (best quality, requires pro license)
                - pyannote/speaker-diarization-community-1 (free, good quality)

        Requires HuggingFace token and license acceptance:
        1. Accept license at https://hf.co/{model_name}
        2. Set MURMURAI_HF_TOKEN in .env
        """
        with cls._lock:
            if model_name not in cls._diarize_models:
                settings = get_settings()
                logger = get_logger()
                logger.info(f"Loading diarization model: {model_name}...")

                pipeline = Pipeline.from_pretrained(
                    model_name,
                    token=settings.hf_token,
                )

                if pipeline is None:
                    raise RuntimeError(
                        f"Failed to load diarization model '{model_name}'. "
                        f"This model is gated on HuggingFace.\n"
                        f"1. Accept license at https://hf.co/{model_name}\n"
                        "2. Set MURMURAI_HF_TOKEN in .env with your HuggingFace token\n"
                        "   Get token at: https://hf.co/settings/tokens"
                    )

                cls._diarize_models[model_name] = pipeline.to(torch.device(settings.device_str))
                logger.info(f"Diarization model '{model_name}' loaded successfully")
            return cls._diarize_models[model_name]

    @classmethod
    def is_loaded(cls) -> bool:
        """Check if the main model is loaded."""
        return cls._model is not None

    @classmethod
    def preload(cls) -> None:
        """Preload the main transcription model."""
        logger = get_logger()
        logger.info("Preloading models at startup...")
        cls.get_model()
        logger.info("Startup preload complete - ready for requests")
