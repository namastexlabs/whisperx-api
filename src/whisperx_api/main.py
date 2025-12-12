"""Main entry point for whisperx-api."""

import uvicorn

from whisperx_api.config import get_settings


def run() -> None:
    """Main entry point - starts API server."""
    settings = get_settings()

    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    print(f"WhisperX API starting on http://{settings.host}:{settings.port}")
    print(f"Model: {settings.model}")
    print(f"Data directory: {settings.data_dir}")
    print("API docs: http://localhost:8000/docs")

    # Start FastAPI server
    uvicorn.run(
        "whisperx_api.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
