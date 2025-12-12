"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MURMURAI_",
        case_sensitive=False,
    )

    # API Authentication (default allows uvx to run without .env)
    api_key: str = "namastex888"

    # Server
    host: str = "0.0.0.0"
    port: int = 8880

    # Model (GPU required)
    model: str = "large-v3-turbo"
    compute_type: str = "float16"
    batch_size: int = 16
    device: int = 0  # GPU index (0, 1, 2, etc. for multi-GPU systems)
    language: str | None = None  # Default language (None = auto-detect, slower)

    @property
    def device_str(self) -> str:
        """CUDA device string (e.g., 'cuda:0', 'cuda:1')."""
        return f"cuda:{self.device}"

    # HuggingFace (for diarization)
    hf_token: str | None = None

    # Storage
    data_dir: Path = Path("./data")

    # Upload limits
    max_upload_size_mb: int = 2048  # 2GB default

    # Pre-loading
    preload_languages: list[str] = []

    # ASR Options (applied at model load time)
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    length_penalty: float = 1.0
    temperatures: str = "0.0,0.2,0.4,0.6,0.8,1.0"  # Comma-separated fallback temps
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = False
    suppress_numerals: bool = False
    initial_prompt: str | None = None
    hotwords: str | None = None

    # VAD Options (applied at model load time)
    vad_method: str = "pyannote"  # "pyannote" or "silero"
    vad_onset: float = 0.5
    vad_offset: float = 0.363
    chunk_size: int = 30

    @property
    def asr_options(self) -> dict:
        """Build ASR options dict for load_model()."""
        return {
            "beam_size": self.beam_size,
            "best_of": self.best_of,
            "patience": self.patience,
            "length_penalty": self.length_penalty,
            "temperatures": [float(t.strip()) for t in self.temperatures.split(",")],
            "compression_ratio_threshold": self.compression_ratio_threshold,
            "log_prob_threshold": self.log_prob_threshold,
            "no_speech_threshold": self.no_speech_threshold,
            "condition_on_previous_text": self.condition_on_previous_text,
            "suppress_numerals": self.suppress_numerals,
            "initial_prompt": self.initial_prompt,
            "hotwords": self.hotwords,
        }

    @property
    def vad_options(self) -> dict:
        """Build VAD options dict for load_model()."""
        return {
            "vad_onset": self.vad_onset,
            "vad_offset": self.vad_offset,
            "chunk_size": self.chunk_size,
        }

    # Startup options
    skip_dependency_check: bool = False  # Skip startup dependency validation

    # Logging
    log_format: str = "text"  # "text" (human-readable) or "json" (structured)
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR

    @property
    def db_path(self) -> Path:
        """SQLite database path."""
        return self.data_dir / "transcripts.db"

    @property
    def max_upload_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get settings instance (cached)."""
    return Settings()
