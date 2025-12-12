"""Shared test fixtures for whisperx-api."""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Reset settings cache between tests."""
    from whisperx_api.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_api_key() -> str:
    """Return test API key."""
    return "test-api-key-12345"


@pytest.fixture
def test_env(test_api_key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up test environment variables."""
    # Change to tmp_path to avoid loading project .env file
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WHISPERX_API_KEY", test_api_key)
    monkeypatch.setenv("WHISPERX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPERX_HOST", "127.0.0.1")
    monkeypatch.setenv("WHISPERX_PORT", "8880")
    # Ensure HF token is not inherited from local .env
    monkeypatch.delenv("WHISPERX_HF_TOKEN", raising=False)


@pytest.fixture
def test_settings(test_env):
    """Get settings configured for testing."""
    from whisperx_api.config import get_settings

    return get_settings()


@pytest_asyncio.fixture
async def initialized_db(test_settings):
    """Initialize database for testing."""
    from whisperx_api.database import init_db

    await init_db()


@pytest_asyncio.fixture
async def async_client(test_env, initialized_db) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing API endpoints."""
    from whisperx_api.server import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def auth_headers(test_api_key: str) -> dict[str, str]:
    """Return headers with valid API key."""
    return {"Authorization": test_api_key}


@pytest.fixture
def mock_gpu_available():
    """Mock torch.cuda.is_available to return True."""
    with patch("torch.cuda.is_available", return_value=True):
        with patch("torch.cuda.get_device_name", return_value="Mock GPU"):
            yield
