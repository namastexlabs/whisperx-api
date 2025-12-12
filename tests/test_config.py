"""Tests for configuration management."""

from pathlib import Path

import pytest


def test_settings_loads_with_env_vars(test_settings):
    """Test that settings load correctly from environment."""
    assert test_settings.api_key == "test-api-key-12345"
    assert test_settings.host == "127.0.0.1"
    assert test_settings.port == 8880


def test_settings_default_values(test_settings):
    """Test that default values are applied correctly."""
    assert test_settings.model == "large-v3-turbo"
    assert test_settings.compute_type == "float16"
    assert test_settings.batch_size == 16
    assert test_settings.hf_token is None


def test_db_path_property(test_settings):
    """Test that db_path property returns correct path."""
    expected = test_settings.data_dir / "transcripts.db"
    assert test_settings.db_path == expected


def test_max_upload_bytes_property(test_settings):
    """Test that max_upload_bytes property returns correct value."""
    expected = test_settings.max_upload_size_mb * 1024 * 1024
    assert test_settings.max_upload_bytes == expected


def test_missing_api_key_exits(monkeypatch, tmp_path):
    """Test that missing API key causes clean exit."""
    from whisperx_api.config import get_settings

    # Clear cache
    get_settings.cache_clear()

    # Remove API key from environment
    monkeypatch.delenv("WHISPERX_API_KEY", raising=False)

    # Create empty .env to prevent loading from project .env
    empty_env = tmp_path / ".env"
    empty_env.touch()
    monkeypatch.chdir(tmp_path)

    # Should exit with code 1
    with pytest.raises(SystemExit) as exc_info:
        get_settings()

    assert exc_info.value.code == 1


def test_data_dir_is_path(test_settings):
    """Test that data_dir is a Path object."""
    assert isinstance(test_settings.data_dir, Path)
