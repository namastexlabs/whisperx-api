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

    # Transcription defaults
    default_task: str = "transcribe"
    default_temperature: float = 0.0
    default_beam_size: int = 5

    # VAD defaults
    default_vad_onset: float = 0.5
    default_vad_offset: float = 0.363
    default_chunk_size: int = 30

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
