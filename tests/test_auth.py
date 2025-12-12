"""Tests for API authentication."""

import pytest
from fastapi import HTTPException

from murmurai_server.auth import verify_api_key


@pytest.mark.asyncio
async def test_valid_api_key(test_settings, test_api_key):
    """Test that valid API key passes verification."""
    result = await verify_api_key(api_key=test_api_key)
    assert result == test_api_key


@pytest.mark.asyncio
async def test_invalid_api_key(test_settings):
    """Test that invalid API key raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(api_key="wrong-api-key")

    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_empty_api_key(test_settings):
    """Test that empty API key raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(api_key="")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_case_sensitive(test_settings, test_api_key):
    """Test that API key comparison is case-sensitive."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(api_key=test_api_key.upper())

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_bearer_prefix_stripped(test_settings, test_api_key):
    """Test that Bearer prefix is properly stripped."""
    result = await verify_api_key(api_key=f"Bearer {test_api_key}")
    assert result == test_api_key


@pytest.mark.asyncio
async def test_bearer_prefix_wrong_key(test_settings):
    """Test that Bearer prefix with wrong key still fails."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(api_key="Bearer wrong-key")

    assert exc_info.value.status_code == 401
