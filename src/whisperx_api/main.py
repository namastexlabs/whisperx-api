"""Main entry point for whisperx-api."""

import argparse
import sys

import uvicorn

from whisperx_api.config import get_settings
from whisperx_api.deps import startup_check


def run() -> None:
    """Main entry point - starts API server."""
    parser = argparse.ArgumentParser(
        description="WhisperX API - GPU-powered transcription service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  whisperx-api                    Start server with default settings
  whisperx-api --force            Start even if dependencies are missing
  whisperx-api --skip-check       Skip dependency check entirely

Environment variables:
  WHISPERX_API_KEY               API authentication key (required)
  WHISPERX_HOST                  Server bind address (default: 0.0.0.0)
  WHISPERX_PORT                  Server port (default: 8880)
  WHISPERX_MODEL                 WhisperX model (default: large-v3-turbo)
  WHISPERX_HF_TOKEN              HuggingFace token for diarization

Full docs: https://github.com/namastexlabs/whisperx-api
""",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Start server even if dependencies are missing",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip dependency check entirely",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    if args.version:
        from whisperx_api import __version__

        print(f"whisperx-api {__version__}")
        sys.exit(0)

    # Run dependency check unless skipped
    if not args.skip_check:
        startup_check(force=args.force)

    settings = get_settings()

    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    print(f"WhisperX API starting on http://{settings.host}:{settings.port}")
    print(f"Model: {settings.model}")
    print(f"Data directory: {settings.data_dir}")
    print(f"API docs: http://{settings.host}:{settings.port}/docs")

    # Start FastAPI server
    uvicorn.run(
        "whisperx_api.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
