"""GPU model singleton manager for transcription models."""

import gc
import hashlib
import json
import threading
from typing import Any

# Import murmurai FIRST - the fork's compat.py applies all patches automatically
# (torch 2.6+, pyannote 4.x, torchaudio 2.9+)
import murmurai as murmurai_core  # type: ignore[import-untyped]
import torch
from pyannote.audio import Pipeline

from murmurai_server.config import get_settings
from murmurai_server.logging import get_logger

# Default ASR/VAD options (matching murmurai-core defaults)
DEFAULT_ASR_OPTIONS = {
    "beam_size": 5,
    "best_of": 5,
    "patience": 1.0,
    "length_penalty": 1.0,
    "temperatures": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "compression_ratio_threshold": 2.4,
    "log_prob_threshold": -1.0,
    "no_speech_threshold": 0.6,
    "condition_on_previous_text": False,
    "suppress_numerals": False,
    "initial_prompt": None,
    "hotwords": None,
}

DEFAULT_VAD_OPTIONS = {
    "vad_onset": 0.5,
    "vad_offset": 0.363,
    "chunk_size": 30,
}


class ModelManager:
    """Singleton manager for GPU models with hybrid caching.

    Provides fast path for default options (cached model) and slow path
    for custom ASR/VAD options (load fresh or use cached custom model).

    GPU model loading takes 30-60s, so we cache up to 3 custom configs.
    """

    _default_model: Any = None
    _custom_models: dict[str, Any] = {}  # Cache by options hash (max 3)
    _align_models: dict[str, tuple[Any, Any]] = {}
    _diarize_models: dict[str, Any] = {}  # Cache by model name
    _lock = threading.Lock()

    @classmethod
    def _hash_options(
        cls, asr_options: dict | None, vad_options: dict | None, vad_method: str
    ) -> str:
        """Create hash key for model options."""
        data = {
            "asr": asr_options or {},
            "vad": vad_options or {},
            "vad_method": vad_method,
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]

    @classmethod
    def get_model(
        cls,
        asr_options: dict | None = None,
        vad_options: dict | None = None,
        vad_method: str = "pyannote",
    ) -> Any:
        """Get model with specified options, using cache when possible.

        Args:
            asr_options: Custom ASR options dict. None = use defaults (fast path).
            vad_options: Custom VAD options dict. None = use defaults.
            vad_method: VAD method ("pyannote" or "silero").

        Returns:
            FasterWhisperPipeline model configured with specified options.

        Note: Uses "cuda" not "cuda:N" because faster_whisper/ctranslate2
        doesn't support device index in string. torch.cuda.set_device()
        is called at startup to select the correct GPU.
        """
        settings = get_settings()

        # Fast path: use default model (no custom options)
        if asr_options is None and vad_options is None and vad_method == settings.vad_method:
            return cls._get_default_model()

        # Slow path: get/create model with custom options
        return cls._get_custom_model(asr_options, vad_options, vad_method)

    @classmethod
    def _get_default_model(cls) -> Any:
        """Get or load the default model with settings from .env."""
        with cls._lock:
            if cls._default_model is None:
                settings = get_settings()
                logger = get_logger()
                logger.info(f"Loading default model: {settings.model} ({settings.compute_type})...")
                logger.info(f"  VAD method: {settings.vad_method}")
                logger.info(
                    f"  ASR options: beam_size={settings.beam_size}, temps={settings.temperatures}"
                )
                cls._default_model = murmurai_core.load_model(
                    settings.model,
                    device="cuda",
                    compute_type=settings.compute_type,
                    asr_options=settings.asr_options,
                    vad_options=settings.vad_options,
                    vad_method=settings.vad_method,
                )
                logger.info("Default model loaded successfully")
            return cls._default_model

    @classmethod
    def _get_custom_model(
        cls, asr_options: dict | None, vad_options: dict | None, vad_method: str
    ) -> Any:
        """Get or load model with custom options (may be slow on cache miss)."""
        settings = get_settings()
        logger = get_logger()

        # Build full options (merge with defaults)
        full_asr = {**DEFAULT_ASR_OPTIONS, **(asr_options or {})}
        full_vad = {**DEFAULT_VAD_OPTIONS, **(vad_options or {})}
        options_key = cls._hash_options(full_asr, full_vad, vad_method)

        with cls._lock:
            # Check cache
            if options_key in cls._custom_models:
                logger.debug(f"Using cached custom model: {options_key}")
                return cls._custom_models[options_key]

            # Load new model with custom options
            logger.info(f"Loading custom model (key={options_key})...")
            logger.info(f"  VAD method: {vad_method}")
            logger.info(
                f"  ASR: beam_size={full_asr.get('beam_size')}, temps={full_asr.get('temperatures')}"
            )

            model = murmurai_core.load_model(
                settings.model,
                device="cuda",
                compute_type=settings.compute_type,
                asr_options=full_asr,
                vad_options=full_vad,
                vad_method=vad_method,
            )

            # Cache management: limit to 3 custom models
            if len(cls._custom_models) >= 3:
                oldest_key = next(iter(cls._custom_models))
                logger.info(f"Evicting oldest custom model from cache: {oldest_key}")
                del cls._custom_models[oldest_key]
                gc.collect()
                torch.cuda.empty_cache()

            cls._custom_models[options_key] = model
            logger.info(f"Custom model loaded and cached: {options_key}")
            return model

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
    def get_diarize_model(cls, model_name: str = "pyannote/speaker-diarization-community-1") -> Any:
        """Get or load speaker diarization model.

        Args:
            model_name: HuggingFace model ID (default: pyannote/speaker-diarization-community-1)

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
        """Check if the default model is loaded."""
        return cls._default_model is not None

    @classmethod
    def preload(cls) -> None:
        """Preload the default transcription model."""
        logger = get_logger()
        logger.info("Preloading default model at startup...")
        cls._get_default_model()
        logger.info("Startup preload complete - ready for requests")
