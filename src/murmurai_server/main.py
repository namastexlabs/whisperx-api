"""Main entry point for MurmurAI."""

import argparse
import sys

import uvicorn

from murmurai_server.config import get_settings
from murmurai_server.deps import startup_check


def run() -> None:
    """Main entry point - starts API server."""
    parser = argparse.ArgumentParser(
        description="MurmurAI - GPU-powered transcription service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  murmurai                        Start server with default settings
  murmurai --force                Start even if dependencies are missing
  murmurai --skip-check           Skip dependency check entirely

Environment variables:
  MURMURAI_API_KEY               API authentication key (required)
  MURMURAI_HOST                  Server bind address (default: 0.0.0.0)
  MURMURAI_PORT                  Server port (default: 8880)
  MURMURAI_MODEL                 Model name (default: large-v3-turbo)
  MURMURAI_HF_TOKEN              HuggingFace token for diarization

Full docs: https://github.com/namastexlabs/murmurai
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
        from murmurai_server import __version__

        print(f"murmurai {__version__}")
        sys.exit(0)

    # Run dependency check unless skipped
    if not args.skip_check:
        startup_check(force=args.force)

    settings = get_settings()

    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    print(f"MurmurAI starting on http://{settings.host}:{settings.port}")
    print(f"Model: {settings.model}")
    print(f"Data directory: {settings.data_dir}")
    print(f"API docs: http://{settings.host}:{settings.port}/docs")

    # Start FastAPI server
    uvicorn.run(
        "murmurai_server.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
