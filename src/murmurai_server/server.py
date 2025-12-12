"""FastAPI server for MurmurAI transcription."""

import logging as stdlib_logging
import sys
import tempfile
import uuid
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

# Suppress noisy warnings from dependencies
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pyannote")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.serialization")
warnings.filterwarnings("ignore", message=".*weights_only=False.*")
warnings.filterwarnings("ignore", message=".*Model was trained with.*")
warnings.filterwarnings("ignore", message=".*Lightning automatically upgraded.*")

# Reduce lightning/pyannote logging noise
stdlib_logging.getLogger("pytorch_lightning").setLevel(stdlib_logging.WARNING)
stdlib_logging.getLogger("pyannote").setLevel(stdlib_logging.WARNING)

import httpx  # noqa: E402
import torch  # noqa: E402
from fastapi import (  # noqa: E402
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402

from murmurai_server.auth import verify_api_key  # noqa: E402
from murmurai_server.config import get_settings  # noqa: E402
from murmurai_server.database import (  # noqa: E402
    create_transcript,
    delete_transcript,
    get_transcript,
    init_db,
    list_transcripts,
    update_transcript,
)
from murmurai_server.logging import get_logger, setup_logging  # noqa: E402
from murmurai_server.models import (  # noqa: E402
    HealthResponse,
    Pagination,
    ReadyResponse,
    Transcript,
    TranscriptList,
)
from murmurai_server.transcriber import TranscribeOptions, download_audio, transcribe  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - initialize database and preload model on startup."""
    settings = get_settings()

    # Setup structured logging
    setup_logging(log_format=settings.log_format, log_level=settings.log_level)
    logger = get_logger()

    # Security warning for default API key (print for high visibility)
    if settings.api_key == "namastex888":
        print("\n" + "=" * 70)
        print("[SECURITY] Using default API key 'namastex888'")
        print("[SECURITY] This key is publicly known - anyone can access your API!")
        print("[SECURITY] For production, set: MURMURAI_API_KEY=<your-secure-key>")
        print("[SECURITY] Docs: https://github.com/namastexlabs/murmurai#security")
        print("=" * 70 + "\n")

    # Run dependency checks (unless skipped)
    if not settings.skip_dependency_check:
        from murmurai_server.deps import print_dependency_report, validate_dependencies

        # Check if diarization is likely to be used (preload_languages implies heavy usage)
        require_diarization = bool(settings.preload_languages)
        statuses = validate_dependencies(require_diarization=require_diarization)

        if not print_dependency_report(statuses):
            logger.error("Required dependencies missing. See above for install instructions.")
            logger.error("To skip this check: MURMURAI_SKIP_DEPENDENCY_CHECK=true")
            sys.exit(1)

    # Set default CUDA device if available
    if torch.cuda.is_available():
        torch.cuda.set_device(settings.device)
        logger.info(f"Using GPU [{settings.device}]: {torch.cuda.get_device_name(settings.device)}")

    await init_db()

    # Preload model (takes 30-60s but makes first request fast)
    from murmurai_server.model_manager import ModelManager

    ModelManager.preload()

    # Preload alignment models for configured languages
    if settings.preload_languages:
        logger.info(f"Preloading alignment models for: {settings.preload_languages}")
        for lang in settings.preload_languages:
            try:
                ModelManager.get_align_model(lang)
                logger.info(f"  Alignment model loaded: {lang}")
            except Exception as e:
                logger.warning(f"  Failed to load alignment model {lang}: {e}")

    yield


app = FastAPI(
    title="MurmurAI",
    version="1.0.0",
    description="GPU-powered transcription service with speaker diarization",
    lifespan=lifespan,
    swagger_ui_parameters={
        "tryItOutEnabled": True,  # Enable "Try it out" by default
        "defaultModelsExpandDepth": -1,  # Collapse models by default
        "docExpansion": "list",  # Show operations as list
        "filter": True,  # Enable search filter
    },
)


# Health endpoints (no auth required)


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyResponse)
def ready() -> dict[str, str]:
    """GPU readiness check endpoint."""
    if not torch.cuda.is_available():
        raise HTTPException(status_code=503, detail="GPU not available")

    settings = get_settings()
    return {
        "status": "ready",
        "gpu": torch.cuda.get_device_name(settings.device),
        "model": settings.model,
    }


# Background transcription task


def process_transcription(
    transcript_id: str,
    audio_path: Path,
    options: TranscribeOptions,
    audio_url: str | None,
    webhook_url: str | None,
    webhook_auth_header: str | None,
) -> None:
    """Background task for transcription processing."""
    import asyncio

    async def update_progress(progress: float) -> None:
        await update_transcript(transcript_id, progress=progress)

    def sync_progress_callback(progress: float) -> None:
        asyncio.run(update_progress(progress))

    try:
        # Update status to processing
        asyncio.run(update_transcript(transcript_id, status="processing", progress=0.05))

        # Run transcription pipeline with progress updates
        result = transcribe(
            audio_path=audio_path,
            options=options,
            progress_callback=sync_progress_callback,
        )

        # Save completed result
        asyncio.run(
            update_transcript(
                transcript_id,
                status="completed",
                text=result["text"],
                words=result["words"],
                utterances=result["utterances"],
                confidence=result["confidence"],
                audio_duration=result["audio_duration"],
                language_code=result["language_code"],
                progress=1.0,
            )
        )

        # Send webhook if configured
        if webhook_url:
            asyncio.run(send_webhook(transcript_id, webhook_url, webhook_auth_header))

    except Exception as e:
        # Save error status
        asyncio.run(
            update_transcript(
                transcript_id,
                status="error",
                error=str(e),
                progress=0.0,
            )
        )

        # Send webhook even on error
        if webhook_url:
            asyncio.run(send_webhook(transcript_id, webhook_url, webhook_auth_header))

    finally:
        # Cleanup temp file
        if audio_path and audio_path.exists():
            audio_path.unlink(missing_ok=True)


async def send_webhook(transcript_id: str, webhook_url: str, auth_header: str | None) -> None:
    """Send webhook notification with transcript result."""
    logger = get_logger()
    try:
        result = await get_transcript(transcript_id)
        if not result:
            return

        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header

        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(webhook_url, json=result, headers=headers)
    except Exception as e:
        # Log but don't fail on webhook errors
        logger.warning(f"Webhook failed for {transcript_id}: {e}")


# Transcript endpoints (auth required)


@app.post(
    "/v1/transcript",
    response_model=Transcript,
    dependencies=[Depends(verify_api_key)],
)
async def submit_transcript(
    background_tasks: BackgroundTasks,
    # File upload (optional) - REQUIRED: either file or audio_url
    file: Annotated[UploadFile | None, File(description="Audio file to transcribe")] = None,
    audio_url: Annotated[
        str | None, Form(description="URL to download audio from", examples=[""])
    ] = None,
    # All optional parameters with defaults
    language_code: Annotated[
        str | None, Form(description="Language code (auto-detect if empty)", examples=[""])
    ] = None,
    speaker_labels: Annotated[bool, Form(description="Enable speaker diarization")] = False,
    speakers_expected: Annotated[
        str | None,
        Form(description="Expected number of speakers (leave empty for auto)", examples=[""]),
    ] = None,
    min_speakers: Annotated[
        str | None,
        Form(description="Minimum expected speakers (leave empty for auto)", examples=[""]),
    ] = None,
    max_speakers: Annotated[
        str | None,
        Form(description="Maximum expected speakers (leave empty for auto)", examples=[""]),
    ] = None,
    diarize_model: Annotated[
        str, Form(description="Diarization model (3.1 or community-1)")
    ] = "pyannote/speaker-diarization-3.1",
    return_speaker_embeddings: Annotated[
        bool, Form(description="Include speaker embedding vectors")
    ] = False,
    task: Annotated[str, Form(description="'transcribe' or 'translate'")] = "transcribe",
    initial_prompt: Annotated[
        str | None, Form(description="Prompt for first window", examples=[""])
    ] = None,
    hotwords: Annotated[
        str | None, Form(description="Comma-separated boost words", examples=[""])
    ] = None,
    temperature: Annotated[float, Form(description="Sampling temperature (0=greedy)")] = 0.0,
    temperature_increment_on_fallback: Annotated[
        str | None, Form(description="Temperature increase on decode failure", examples=["0.2"])
    ] = "0.2",
    beam_size: Annotated[int, Form(description="Beam search size")] = 5,
    best_of: Annotated[int, Form(description="Sampling alternatives")] = 5,
    patience: Annotated[float, Form(description="Beam search patience")] = 1.0,
    length_penalty: Annotated[float, Form(description="Length penalty")] = 1.0,
    suppress_tokens: Annotated[
        str | None, Form(description="Comma-separated token IDs to suppress", examples=[""])
    ] = None,
    logprob_threshold: Annotated[
        float, Form(description="Log probability threshold for filtering")
    ] = -1.0,
    word_timestamps: Annotated[bool, Form(description="Include word-level timestamps")] = False,
    return_char_alignments: Annotated[bool, Form(description="Include char alignments")] = False,
    suppress_numerals: Annotated[bool, Form(description="Spell out numbers")] = False,
    interpolate_method: Annotated[
        str, Form(description="Word boundary interpolation: nearest, linear, ignore")
    ] = "nearest",
    compression_ratio_threshold: Annotated[
        float, Form(description="Hallucination filter threshold")
    ] = 2.4,
    no_speech_threshold: Annotated[float, Form(description="Silence detection threshold")] = 0.6,
    condition_on_previous_text: Annotated[
        bool, Form(description="Use previous output as prompt")
    ] = False,
    vad_method: Annotated[str, Form(description="VAD algorithm: pyannote or silero")] = "pyannote",
    vad_onset: Annotated[float, Form(description="VAD speech onset threshold")] = 0.5,
    vad_offset: Annotated[float, Form(description="VAD speech offset threshold")] = 0.363,
    chunk_size: Annotated[int, Form(description="Max chunk duration in seconds")] = 30,
    segment_resolution: Annotated[
        str, Form(description="Segment splitting: sentence or chunk")
    ] = "sentence",
    max_line_width: Annotated[
        str | None, Form(description="Max chars per subtitle line", examples=[""])
    ] = None,
    max_line_count: Annotated[
        str | None, Form(description="Max lines per subtitle segment", examples=[""])
    ] = None,
    highlight_words: Annotated[
        bool, Form(description="Highlight current word in subtitles")
    ] = False,
    webhook_url: Annotated[
        str | None, Form(description="Webhook URL for results", examples=[""])
    ] = None,
    webhook_auth_header: Annotated[
        str | None, Form(description="Webhook Authorization header", examples=[""])
    ] = None,
) -> dict[str, Any]:
    """Submit a new transcription job.

    Accepts either:
    - `file`: Direct file upload (multipart/form-data)
    - `audio_url`: URL to download audio from

    The audio will be transcribed asynchronously.
    Poll GET /v1/transcript/{id} to check status.
    """
    settings = get_settings()

    # Sanitize nullable string fields (convert empty strings to None)
    # This handles Swagger UI sending "" instead of omitting the field
    audio_url = audio_url if audio_url else None
    language_code = language_code if language_code else None
    initial_prompt = initial_prompt if initial_prompt else None
    hotwords = hotwords if hotwords else None
    suppress_tokens = suppress_tokens if suppress_tokens else None
    webhook_url = webhook_url if webhook_url else None
    webhook_auth_header = webhook_auth_header if webhook_auth_header else None

    # Convert speaker count strings to integers (None if empty/invalid)
    # Using str type in Form to show empty in Swagger instead of "0"
    speakers_expected_int: int | None = int(speakers_expected) if speakers_expected else None
    min_speakers_int: int | None = int(min_speakers) if min_speakers else None
    max_speakers_int: int | None = int(max_speakers) if max_speakers else None

    # Convert optional numeric strings
    temp_fallback: float | None = (
        float(temperature_increment_on_fallback) if temperature_increment_on_fallback else None
    )
    max_line_width_int: int | None = int(max_line_width) if max_line_width else None
    max_line_count_int: int | None = int(max_line_count) if max_line_count else None

    # Validate input
    if not file and not audio_url:
        raise HTTPException(status_code=400, detail="Either file or audio_url is required")

    transcript_id = str(uuid.uuid4())

    # Handle file upload
    if file:
        # Validate file size
        if file.size and file.size > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
            )

        # Save to temp file
        suffix = Path(file.filename or "audio").suffix or ".mp3"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        audio_path = Path(temp_file.name)
        audio_url_for_db = f"file://{file.filename}"
    else:
        # Download from URL (in background task)
        assert audio_url is not None  # Validated above
        audio_path = await download_audio(audio_url)
        audio_url_for_db = audio_url

    # Create database record
    result = await create_transcript(
        id=transcript_id,
        audio_url=audio_url_for_db,
        language=language_code,
        speaker_labels=speaker_labels,
        speakers_expected=speakers_expected_int,
        webhook_url=webhook_url,
        webhook_auth_header=webhook_auth_header,
    )

    # Build options (all params already have defaults from Form)
    options = TranscribeOptions(
        language=language_code,
        task=task,
        speaker_labels=speaker_labels,
        speakers_expected=speakers_expected_int,
        min_speakers=min_speakers_int,
        max_speakers=max_speakers_int,
        diarize_model=diarize_model,
        return_speaker_embeddings=return_speaker_embeddings,
        temperature=temperature,
        temperature_increment_on_fallback=temp_fallback,
        beam_size=beam_size,
        best_of=best_of,
        patience=patience,
        length_penalty=length_penalty,
        suppress_tokens=suppress_tokens,
        logprob_threshold=logprob_threshold,
        initial_prompt=initial_prompt,
        hotwords=hotwords,
        word_timestamps=word_timestamps,
        return_char_alignments=return_char_alignments,
        suppress_numerals=suppress_numerals,
        interpolate_method=interpolate_method,
        compression_ratio_threshold=compression_ratio_threshold,
        no_speech_threshold=no_speech_threshold,
        condition_on_previous_text=condition_on_previous_text,
        vad_method=vad_method,
        vad_onset=vad_onset,
        vad_offset=vad_offset,
        chunk_size=chunk_size,
        segment_resolution=segment_resolution,
        max_line_width=max_line_width_int,
        max_line_count=max_line_count_int,
        highlight_words=highlight_words,
    )

    # Queue background task
    background_tasks.add_task(
        process_transcription,
        transcript_id=transcript_id,
        audio_path=audio_path,
        options=options,
        audio_url=audio_url_for_db,
        webhook_url=webhook_url,
        webhook_auth_header=webhook_auth_header,
    )

    return result


@app.get(
    "/v1/transcript/{transcript_id}",
    response_model=Transcript,
    dependencies=[Depends(verify_api_key)],
)
async def get_transcript_endpoint(transcript_id: str) -> dict[str, Any]:
    """Get transcript status and result."""
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return result


@app.get(
    "/v1/transcript/{transcript_id}/srt",
    dependencies=[Depends(verify_api_key)],
)
async def get_srt(transcript_id: str) -> PlainTextResponse:
    """Export transcript as SRT subtitles."""
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    if result["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    srt_content = generate_srt(result.get("utterances") or [])
    return PlainTextResponse(srt_content, media_type="text/srt")


@app.get(
    "/v1/transcript/{transcript_id}/vtt",
    dependencies=[Depends(verify_api_key)],
)
async def get_vtt(transcript_id: str) -> PlainTextResponse:
    """Export transcript as WebVTT subtitles."""
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    if result["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    vtt_content = generate_vtt(result.get("utterances") or [])
    return PlainTextResponse(vtt_content, media_type="text/vtt")


@app.get(
    "/v1/transcript/{transcript_id}/txt",
    dependencies=[Depends(verify_api_key)],
)
async def get_txt(transcript_id: str) -> PlainTextResponse:
    """Export transcript as plain text."""
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    if result["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    return PlainTextResponse(result.get("text") or "", media_type="text/plain")


@app.get(
    "/v1/transcript/{transcript_id}/json",
    dependencies=[Depends(verify_api_key)],
)
async def get_json(transcript_id: str) -> JSONResponse:
    """Export full transcript as JSON download."""
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    if result["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    return JSONResponse(
        content=result,
        headers={"Content-Disposition": f'attachment; filename="{transcript_id}.json"'},
    )


@app.get(
    "/v1/transcript/{transcript_id}/tsv",
    dependencies=[Depends(verify_api_key)],
)
async def get_tsv(transcript_id: str) -> PlainTextResponse:
    """Export transcript as tab-separated values.

    Format: start<tab>end<tab>speaker<tab>text
    Times are in milliseconds.
    """
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    if result["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    tsv_content = generate_tsv(result.get("utterances") or [])
    return PlainTextResponse(
        tsv_content,
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": f'attachment; filename="{transcript_id}.tsv"'},
    )


@app.get(
    "/v1/transcript/{transcript_id}/words",
    dependencies=[Depends(verify_api_key)],
)
async def get_words(transcript_id: str) -> JSONResponse:
    """Export word-level timestamps."""
    result = await get_transcript(transcript_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcript not found")
    if result["status"] != "completed":
        raise HTTPException(status_code=400, detail="Transcript not ready")

    return JSONResponse(content={"words": result.get("words") or []})


@app.get(
    "/v1/transcript",
    response_model=TranscriptList,
    dependencies=[Depends(verify_api_key)],
)
async def list_transcripts_endpoint(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
) -> dict[str, Any]:
    """List transcripts with optional status filter and pagination."""
    transcripts, total = await list_transcripts(limit=limit, offset=offset, status=status)
    return {
        "transcripts": transcripts,
        "pagination": Pagination(total=total, limit=limit, offset=offset),
    }


@app.delete(
    "/v1/transcript/{transcript_id}",
    dependencies=[Depends(verify_api_key)],
)
async def delete_transcript_endpoint(transcript_id: str) -> dict[str, str]:
    """Delete a transcript."""
    deleted = await delete_transcript(transcript_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"id": transcript_id, "status": "deleted"}


# Subtitle generation helpers


def generate_srt(utterances: list[dict[str, Any]]) -> str:
    """Generate SRT subtitle format from utterances."""
    lines = []
    for i, utterance in enumerate(utterances, 1):
        start = format_timestamp_srt(utterance["start"])
        end = format_timestamp_srt(utterance["end"])
        text = utterance["text"]
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def generate_vtt(utterances: list[dict[str, Any]]) -> str:
    """Generate WebVTT subtitle format from utterances."""
    lines = ["WEBVTT\n"]
    for utterance in utterances:
        start = format_timestamp_vtt(utterance["start"])
        end = format_timestamp_vtt(utterance["end"])
        text = utterance["text"]
        lines.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def format_timestamp_srt(ms: int) -> str:
    """Format milliseconds as SRT timestamp (HH:MM:SS,mmm)."""
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_timestamp_vtt(ms: int) -> str:
    """Format milliseconds as VTT timestamp (HH:MM:SS.mmm)."""
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def generate_tsv(utterances: list[dict[str, Any]]) -> str:
    """Generate TSV format from utterances.

    Format: start<tab>end<tab>speaker<tab>text
    Times are in milliseconds.
    """
    lines = ["start\tend\tspeaker\ttext"]  # Header
    for utterance in utterances:
        start = utterance["start"]
        end = utterance["end"]
        speaker = utterance.get("speaker", "")
        # Escape tabs and newlines in text
        text = utterance["text"].replace("\t", " ").replace("\n", " ")
        lines.append(f"{start}\t{end}\t{speaker}\t{text}")
    return "\n".join(lines)
