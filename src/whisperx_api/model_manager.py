"""GPU model singleton manager for WhisperX models."""

import warnings

# Suppress pyannote version mismatch warnings (models work fine despite version differences)
warnings.filterwarnings("ignore", message="Model was trained with")
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
warnings.filterwarnings("ignore", category=UserWarning, module="pytorch_lightning")

# =============================================================================
# CRITICAL: Torch 2.6+ compatibility patch - MUST run before pyannote imports!
# =============================================================================
# Torch 2.6+ changed weights_only=True as default for torch.load().
# Pyannote/lightning models serialize custom types that need weights_only=False.
# We patch lightning's cloud_io module to force weights_only=False.
# =============================================================================
import torch


def _patched_load(path_or_url, map_location=None, **kwargs):
    """Patched load that uses weights_only=False for trusted pyannote models."""
    kwargs.pop("weights_only", None)
    return torch.load(path_or_url, map_location=map_location, weights_only=False, **kwargs)


# Patch lightning's cloud_io._load AND the pl_load reference in saving.py
# The saving module imports _load as pl_load at import time, so we need to patch both.
_patched_modules = []

try:
    import lightning.fabric.utilities.cloud_io as cloud_io

    cloud_io._load = _patched_load
    _patched_modules.append("lightning.fabric.utilities.cloud_io")
except ImportError:
    pass

try:
    import lightning.pytorch.core.saving as saving

    saving.pl_load = _patched_load
    _patched_modules.append("lightning.pytorch.core.saving.pl_load")
except ImportError:
    pass

try:
    import lightning_fabric.utilities.cloud_io as cloud_io2

    cloud_io2._load = _patched_load
    _patched_modules.append("lightning_fabric.utilities.cloud_io")
except ImportError:
    pass

if _patched_modules:
    print(f"[whisperx-api] Patched torch 2.6+ compatibility: {', '.join(_patched_modules)}")
else:
    print("[whisperx-api] Warning: Could not patch lightning (not found)")

# =============================================================================
# CRITICAL: whisperx/pyannote 4.x compatibility patch
# =============================================================================
# whisperx 3.x uses `use_auth_token` parameter, but pyannote 4.x renamed it to `token`.
# We patch pyannote's VoiceActivityDetection to accept the old parameter name.
# =============================================================================
try:
    from pyannote.audio.pipelines import voice_activity_detection as vad_module

    _original_vad_init = vad_module.VoiceActivityDetection.__init__

    def _patched_vad_init(self, segmentation=None, fscore=False, **inference_kwargs):
        """Patched __init__ that converts use_auth_token to token for pyannote 4.x."""
        # Convert deprecated use_auth_token to token
        if "use_auth_token" in inference_kwargs:
            inference_kwargs["token"] = inference_kwargs.pop("use_auth_token")
        return _original_vad_init(
            self, segmentation=segmentation, fscore=fscore, **inference_kwargs
        )

    vad_module.VoiceActivityDetection.__init__ = _patched_vad_init
    _patched_modules.append("pyannote.vad.use_auth_token")
except (ImportError, AttributeError):
    pass

# Also patch Inference class directly (used in multiple places)
try:
    from pyannote.audio.core import inference as inference_module

    _original_inference_init = inference_module.Inference.__init__

    def _patched_inference_init(self, model, *args, **kwargs):
        """Patched __init__ that converts use_auth_token to token for pyannote 4.x."""
        if "use_auth_token" in kwargs:
            kwargs["token"] = kwargs.pop("use_auth_token")
        return _original_inference_init(self, model, *args, **kwargs)

    inference_module.Inference.__init__ = _patched_inference_init
    _patched_modules.append("pyannote.inference.use_auth_token")
except (ImportError, AttributeError):
    pass

if "pyannote" in " ".join(_patched_modules):
    print("[whisperx-api] Patched whisperx/pyannote 4.x compatibility")

# =============================================================================
# Now safe to import pyannote (will use patched torch.load)
# =============================================================================
import threading
from typing import Any

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
