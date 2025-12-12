"""API key authentication."""

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from murmurai_server.config import get_settings

api_key_header = APIKeyHeader(name="Authorization", auto_error=True)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key from Authorization header.

    Supports both formats:
    - Raw API key
    - Bearer token: "Bearer <api_key>"

    Uses timing-safe comparison to prevent timing attacks.
    """
    # Strip "Bearer " prefix if present
    if api_key.startswith("Bearer "):
        api_key = api_key[7:]

    settings = get_settings()
    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
