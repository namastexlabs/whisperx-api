"""WhisperX transcription pipeline wrapper."""

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd


def _ensure_ffmpeg() -> None:
    """Ensure ffmpeg is available, using bundled version if needed."""
    if shutil.which("ffmpeg"):
        return  # System ffmpeg available

    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg_path = get_ffmpeg_exe()

        # Create symlink directory with proper 'ffmpeg' name
        # (imageio_ffmpeg binary has versioned name like ffmpeg-linux-x86_64-v7.0.2)
        symlink_dir = Path(tempfile.gettempdir()) / "whisperx-api-ffmpeg"
        symlink_dir.mkdir(exist_ok=True)
        symlink_path = symlink_dir / "ffmpeg"

        # Create/update symlink
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(ffmpeg_path)

        # Add to PATH
        os.environ["PATH"] = str(symlink_dir) + os.pathsep + os.environ.get("PATH", "")
        print(f"[whisperx-api] Using bundled ffmpeg: {ffmpeg_path}")
    except Exception as e:
        print(f"[whisperx-api] WARNING: Could not setup bundled ffmpeg: {e}")


# Ensure ffmpeg is available BEFORE importing whisperx
_ensure_ffmpeg()

import whisperx  # noqa: E402

from whisperx_api.config import get_settings  # noqa: E402
from whisperx_api.model_manager import ModelManager  # noqa: E402


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

    # Decoding parameters
    temperature: float = 0.0
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    length_penalty: float = 1.0

    # Prompt engineering
    initial_prompt: str | None = None
    hotwords: str | None = None

    # Output control
    word_timestamps: bool = False
    return_char_alignments: bool = False
    suppress_numerals: bool = False

    # Hallucination filtering
    compression_ratio_threshold: float = 2.4
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = False

    # VAD parameters
    vad_onset: float = 0.5
    vad_offset: float = 0.363
    chunk_size: int = 30


def convert_pyannote_to_whisperx(diarization: Any) -> pd.DataFrame:
    """Convert pyannote Annotation to whisperx diarize_segments format.

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
    """
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
    """Run WhisperX transcription pipeline.

    Args:
        audio_path: Path to audio file.
        options: Transcription options.
        progress_callback: Optional callback(progress: float) for progress updates.

    Returns:
        Formatted transcript result with words and utterances.
    """
    settings = get_settings()

    # Log job start
    print(f"[whisperx-api] Job started: {audio_path.name}")
    print(f"[whisperx-api]   Language: {options.language or 'auto-detect'}")
    print(f"[whisperx-api]   Speaker labels: {options.speaker_labels}")
    print(f"[whisperx-api]   Word timestamps: {options.word_timestamps}")

    model = ModelManager.get_model()

    # Use request language, fall back to config default, then auto-detect
    effective_language = options.language or settings.language

    # Load audio
    audio = whisperx.load_audio(str(audio_path))

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

    # VAD options (these are passed to the asr options in whisperx)
    asr_options: dict[str, Any] = {}
    if options.initial_prompt:
        asr_options["initial_prompt"] = options.initial_prompt
    if options.hotwords:
        asr_options["hotwords"] = options.hotwords
    if options.suppress_numerals:
        asr_options["suppress_numerals"] = options.suppress_numerals
    if options.temperature != 0.0:
        asr_options["temperatures"] = [options.temperature]
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

    # VAD options
    vad_options: dict[str, Any] = {}
    if options.vad_onset != 0.5:
        vad_options["vad_onset"] = options.vad_onset
    if options.vad_offset != 0.363:
        vad_options["vad_offset"] = options.vad_offset
    if options.chunk_size != 30:
        transcribe_kwargs["chunk_size"] = options.chunk_size

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
        result = whisperx.align(
            result["segments"],
            align_model,
            metadata,
            audio,
            device="cuda",
            return_char_alignments=options.return_char_alignments,
        )

    if progress_callback:
        progress_callback(0.8)  # Alignment done

    # Speaker diarization (if requested)
    if options.speaker_labels:
        diarize_model = ModelManager.get_diarize_model()

        # Determine min/max speakers
        min_spk = options.min_speakers
        max_spk = options.max_speakers
        if options.speakers_expected is not None:
            min_spk = min_spk or options.speakers_expected
            max_spk = max_spk or options.speakers_expected

        # Pass waveform dict to avoid file re-read
        # pyannote 4.x expects torch Tensor, whisperx returns numpy array
        import torch

        waveform = torch.from_numpy(audio[None, :])
        diarization = diarize_model(
            {"waveform": waveform, "sample_rate": 16000},
            min_speakers=min_spk,
            max_speakers=max_spk,
        )
        # Convert pyannote output to whisperx format
        diarize_segments = convert_pyannote_to_whisperx(diarization)
        result = whisperx.assign_word_speakers(diarize_segments, result)

    if progress_callback:
        progress_callback(0.95)  # Diarization done

    formatted = format_result(result, detected_language)

    if progress_callback:
        progress_callback(1.0)  # Complete

    # Log job completion
    segment_count = len(result.get("segments", []))
    word_count = len(formatted.get("words", []))
    print(f"[whisperx-api] Job completed: {segment_count} segments, {word_count} words")
    print(f"[whisperx-api]   Detected language: {detected_language}")

    return formatted


def format_result(result: dict[str, Any], language: str) -> dict[str, Any]:
    """Format WhisperX result to API response format.

    Args:
        result: Raw WhisperX result with segments.
        language: Detected/specified language code.

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

    return {
        "text": full_text,
        "words": words,
        "utterances": utterances,
        "confidence": total_confidence,
        "audio_duration": audio_duration,
        "language_code": language,
    }
