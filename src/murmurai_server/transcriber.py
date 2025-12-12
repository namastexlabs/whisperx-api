"""Transcription pipeline wrapper."""

import ipaddress
import os
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pandas as pd

# SSRF Protection: Block internal/private IP ranges and metadata endpoints
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",  # AWS/GCP metadata
    "metadata.google.internal",  # GCP metadata
    "metadata.azure.internal",  # Azure metadata
}

ALLOWED_SCHEMES = {"http", "https"}


def validate_audio_url(url: str) -> None:
    """Validate audio URL for SSRF protection.

    Args:
        url: URL to validate.

    Raises:
        ValueError: If URL is invalid or points to a blocked host.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Must be http or https.")

    # Check hostname exists
    if not parsed.hostname:
        raise ValueError("Invalid URL: no hostname")

    hostname = parsed.hostname.lower()

    # Check against blocklist
    if hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname}")

    # Resolve hostname and check if it's a private IP
    try:
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in resolved_ips:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)

            # Block private, loopback, link-local, and reserved IPs
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"Blocked IP address: {ip_str} (resolved from {hostname})")
    except socket.gaierror:
        # If DNS resolution fails, let it proceed (httpx will fail with better error)
        pass


def _ensure_ffmpeg() -> None:
    """Ensure ffmpeg is available, using bundled version if needed."""
    if shutil.which("ffmpeg"):
        return  # System ffmpeg available

    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg_path = get_ffmpeg_exe()

        # Create symlink directory with proper 'ffmpeg' name
        # (imageio_ffmpeg binary has versioned name like ffmpeg-linux-x86_64-v7.0.2)
        symlink_dir = Path(tempfile.gettempdir()) / "murmurai-ffmpeg"
        symlink_dir.mkdir(exist_ok=True)
        symlink_path = symlink_dir / "ffmpeg"

        # Create/update symlink
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(ffmpeg_path)

        # Add to PATH
        os.environ["PATH"] = str(symlink_dir) + os.pathsep + os.environ.get("PATH", "")
        # Note: Can't use logger here - runs before logging is setup
    except Exception as e:
        # Note: Can't use logger here - runs before logging is setup
        import sys

        print(f"[murmurai] WARNING: Could not setup bundled ffmpeg: {e}", file=sys.stderr)


# Ensure ffmpeg is available BEFORE importing murmurai-core
_ensure_ffmpeg()

import murmurai as murmurai_core  # type: ignore[import-untyped]  # noqa: E402

from murmurai_server.config import get_settings  # noqa: E402
from murmurai_server.logging import get_logger  # noqa: E402
from murmurai_server.model_manager import ModelManager  # noqa: E402


@dataclass
class TranscribeOptions:
    """Options for transcription pipeline."""

    # Language
    language: str | None = None

    # Task
    task: str = "transcribe"

    # Speaker diarization
    speaker_labels: bool = False
    speakers_expected: int | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None
    diarize_model: str = "pyannote/speaker-diarization-3.1"
    return_speaker_embeddings: bool = False

    # Decoding parameters
    temperature: float = 0.0
    temperature_increment_on_fallback: float | None = 0.2
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    length_penalty: float = 1.0
    suppress_tokens: str | None = None
    logprob_threshold: float | None = -1.0

    # Prompt engineering
    initial_prompt: str | None = None
    hotwords: str | None = None

    # Output control
    word_timestamps: bool = False
    return_char_alignments: bool = False
    suppress_numerals: bool = False
    interpolate_method: str = "nearest"

    # Hallucination filtering
    compression_ratio_threshold: float = 2.4
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = False

    # VAD parameters
    vad_method: str = "pyannote"
    vad_onset: float = 0.5
    vad_offset: float = 0.363
    chunk_size: int = 30

    # Subtitle/segment formatting
    segment_resolution: str = "sentence"
    max_line_width: int | None = None
    max_line_count: int | None = None
    highlight_words: bool = False


def convert_pyannote_to_murmurai(diarization: Any) -> pd.DataFrame:
    """Convert pyannote Annotation to diarize_segments format.

    Args:
        diarization: pyannote.core.Annotation or pyannote 4.x DiarizeOutput.

    Returns:
        pandas DataFrame with columns: start, end, speaker
    """
    # pyannote 4.x returns DiarizeOutput, extract the annotation
    annotation = getattr(diarization, "speaker_diarization", diarization)

    segments = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        segments.append(
            {
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker,
            }
        )
    return pd.DataFrame(segments)


async def download_audio(url: str) -> Path:
    """Download audio from URL to temporary file with streaming.

    Args:
        url: URL to download audio from.

    Returns:
        Path to the downloaded temporary file.

    Raises:
        ValueError: If URL fails SSRF validation.
        httpx.HTTPError: If download fails.
    """
    # SSRF protection: validate URL before downloading
    validate_audio_url(url)

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()

            # Determine file extension from URL or default to .mp3
            url_path = Path(url.split("?")[0])  # Remove query params
            suffix = url_path.suffix if url_path.suffix else ".mp3"

            # Create temp file and stream content
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            async for chunk in response.aiter_bytes():
                temp_file.write(chunk)
            temp_file.close()

            return Path(temp_file.name)


def transcribe(
    audio_path: Path,
    options: TranscribeOptions,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Run transcription pipeline.

    Args:
        audio_path: Path to audio file.
        options: Transcription options.
        progress_callback: Optional callback(progress: float) for progress updates.

    Returns:
        Formatted transcript result with words and utterances.
    """
    settings = get_settings()
    logger = get_logger()

    # Log job start
    logger.info(
        f"Job started: {audio_path.name}",
        extra={
            "language": options.language or "auto-detect",
            "speaker_labels": options.speaker_labels,
            "word_timestamps": options.word_timestamps,
        },
    )
    logger.debug(f"  Language: {options.language or 'auto-detect'}")
    logger.debug(f"  Speaker labels: {options.speaker_labels}")
    logger.debug(f"  Word timestamps: {options.word_timestamps}")

    model = ModelManager.get_model()

    # Use request language, fall back to config default, then auto-detect
    effective_language = options.language or settings.language

    # Load audio
    audio = murmurai_core.load_audio(str(audio_path))

    if progress_callback:
        progress_callback(0.1)  # Audio loaded

    # Build transcription kwargs
    transcribe_kwargs: dict[str, Any] = {
        "batch_size": settings.batch_size,
        "language": effective_language,
    }

    # Add optional parameters if non-default
    if options.task != "transcribe":
        transcribe_kwargs["task"] = options.task

    # ASR decoding options
    asr_options: dict[str, Any] = {}
    if options.initial_prompt:
        asr_options["initial_prompt"] = options.initial_prompt
    if options.hotwords:
        asr_options["hotwords"] = options.hotwords
    if options.suppress_numerals:
        asr_options["suppress_numerals"] = options.suppress_numerals

    # Temperature handling with fallback increment
    if options.temperature != 0.0 or options.temperature_increment_on_fallback is not None:
        temps = [options.temperature]
        if options.temperature_increment_on_fallback is not None:
            # Add fallback temperatures up to 1.0
            t = options.temperature + options.temperature_increment_on_fallback
            while t <= 1.0:
                temps.append(t)
                t += options.temperature_increment_on_fallback
        asr_options["temperatures"] = temps

    if options.beam_size != 5:
        asr_options["beam_size"] = options.beam_size
    if options.best_of != 5:
        asr_options["best_of"] = options.best_of
    if options.patience != 1.0:
        asr_options["patience"] = options.patience
    if options.length_penalty != 1.0:
        asr_options["length_penalty"] = options.length_penalty
    if options.compression_ratio_threshold != 2.4:
        asr_options["compression_ratio_threshold"] = options.compression_ratio_threshold
    if options.no_speech_threshold != 0.6:
        asr_options["no_speech_threshold"] = options.no_speech_threshold
    if options.condition_on_previous_text:
        asr_options["condition_on_previous_text"] = True

    # Additional ASR options from new parameters
    if options.suppress_tokens:
        # Parse comma-separated token IDs
        token_ids = [int(t.strip()) for t in options.suppress_tokens.split(",") if t.strip()]
        if token_ids:
            asr_options["suppress_tokens"] = token_ids
    if options.logprob_threshold is not None and options.logprob_threshold != -1.0:
        asr_options["log_prob_threshold"] = options.logprob_threshold

    # VAD options
    vad_options: dict[str, Any] = {}
    if options.vad_onset != 0.5:
        vad_options["vad_onset"] = options.vad_onset
    if options.vad_offset != 0.363:
        vad_options["vad_offset"] = options.vad_offset
    if options.chunk_size != 30:
        transcribe_kwargs["chunk_size"] = options.chunk_size

    # VAD method selection (pyannote default, silero is lighter alternative)
    if options.vad_method != "pyannote":
        transcribe_kwargs["vad_method"] = options.vad_method

    if asr_options:
        transcribe_kwargs["asr_options"] = asr_options
    if vad_options:
        transcribe_kwargs["vad_options"] = vad_options

    # Transcribe
    result = model.transcribe(audio, **transcribe_kwargs)

    if progress_callback:
        progress_callback(0.5)  # Transcription done

    # Get detected or specified language
    detected_language = result["language"]

    # Align for word-level timestamps (if enabled)
    if options.word_timestamps:
        align_model, metadata = ModelManager.get_align_model(detected_language)
        result = murmurai_core.align(
            result["segments"],
            align_model,
            metadata,
            audio,
            device="cuda",
            return_char_alignments=options.return_char_alignments,
            interpolate_method=options.interpolate_method,
        )

    if progress_callback:
        progress_callback(0.8)  # Alignment done

    # Speaker diarization (if requested)
    speaker_embeddings = None
    if options.speaker_labels:
        diarize_pipeline = ModelManager.get_diarize_model(options.diarize_model)

        # Determine min/max speakers
        min_spk = options.min_speakers
        max_spk = options.max_speakers
        if options.speakers_expected is not None:
            min_spk = min_spk or options.speakers_expected
            max_spk = max_spk or options.speakers_expected

        # Pass waveform dict to avoid file re-read
        # pyannote 4.x expects torch Tensor, murmurai returns numpy array
        import torch

        waveform = torch.from_numpy(audio[None, :])
        diarization = diarize_pipeline(
            {"waveform": waveform, "sample_rate": 16000},
            min_speakers=min_spk,
            max_speakers=max_spk,
            return_embeddings=options.return_speaker_embeddings,
        )

        # Extract speaker embeddings if requested
        if options.return_speaker_embeddings and hasattr(diarization, "embeddings"):
            speaker_embeddings = {
                speaker: emb.tolist() for speaker, emb in diarization.embeddings.items()
            }

        # Convert pyannote output to murmurai format
        diarize_segments = convert_pyannote_to_murmurai(diarization)
        result = murmurai_core.assign_word_speakers(diarize_segments, result)

    if progress_callback:
        progress_callback(0.95)  # Diarization done

    formatted = format_result(result, detected_language, speaker_embeddings)

    if progress_callback:
        progress_callback(1.0)  # Complete

    # Log job completion
    segment_count = len(result.get("segments", []))
    word_count = len(formatted.get("words", []))
    logger.info(
        f"Job completed: {segment_count} segments, {word_count} words",
        extra={
            "segments": segment_count,
            "words": word_count,
            "language": detected_language,
        },
    )

    return formatted


def format_result(
    result: dict[str, Any],
    language: str,
    speaker_embeddings: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    """Format result to API response format.

    Args:
        result: Raw result with segments.
        language: Detected/specified language code.
        speaker_embeddings: Optional speaker embedding vectors.

    Returns:
        Formatted transcript with words and utterances.
    """
    words: list[dict[str, Any]] = []
    utterances: list[dict[str, Any]] = []

    for segment in result.get("segments", []):
        speaker = segment.get("speaker", "A")
        utterance_words: list[dict[str, Any]] = []

        for word in segment.get("words", []):
            word_data = {
                "text": word.get("word", ""),
                "start": int(word.get("start", 0) * 1000),  # Convert to ms
                "end": int(word.get("end", 0) * 1000),
                "confidence": word.get("score", 0.0),
                "speaker": speaker,
            }
            words.append(word_data)
            utterance_words.append(word_data)

        # Build utterance from segment
        if utterance_words:
            avg_confidence = sum(w["confidence"] for w in utterance_words) / len(utterance_words)
        else:
            avg_confidence = 0.0

        utterances.append(
            {
                "speaker": speaker,
                "text": segment.get("text", "").strip(),
                "start": int(segment.get("start", 0) * 1000),
                "end": int(segment.get("end", 0) * 1000),
                "confidence": avg_confidence,
                "words": utterance_words,
            }
        )

    # Calculate overall metrics
    full_text = " ".join(s.get("text", "").strip() for s in result.get("segments", []))
    total_confidence = sum(w["confidence"] for w in words) / len(words) if words else 0
    audio_duration = max((w["end"] for w in words), default=0)

    formatted = {
        "text": full_text,
        "words": words,
        "utterances": utterances,
        "confidence": total_confidence,
        "audio_duration": audio_duration,
        "language_code": language,
    }

    # Include speaker embeddings if available
    if speaker_embeddings:
        formatted["speaker_embeddings"] = speaker_embeddings

    return formatted
