"""Pydantic models for API request/response."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class TranscriptParams(BaseModel):
    """Request body for creating a transcript.

    Supports both URL and file upload (file handled separately in endpoint).
    All parameters are optional - sensible defaults are applied server-side.
    """

    # Audio source (URL - file upload handled via multipart form)
    audio_url: HttpUrl | None = None

    # Language settings
    language_code: str | None = None

    # Speaker diarization
    speaker_labels: bool | None = Field(None, description="Enable speaker diarization (default: false)")
    speakers_expected: int | None = Field(None, description="Expected number of speakers (sets both min and max)")
    min_speakers: int | None = Field(None, description="Minimum expected speakers")
    max_speakers: int | None = Field(None, description="Maximum expected speakers")

    # Transcription task
    task: Literal["transcribe", "translate"] | None = Field(
        None,
        description="'transcribe' for same language, 'translate' to English (default: transcribe)"
    )

    # Decoding parameters
    temperature: float | None = Field(None, ge=0.0, le=1.0, description="Sampling temperature (default: 0.0)")
    beam_size: int | None = Field(None, ge=1, le=10, description="Beam search size (default: 5)")
    best_of: int | None = Field(None, ge=1, description="Number of sampling alternatives (default: 5)")
    patience: float | None = Field(None, ge=0.0, description="Beam search patience factor (default: 1.0)")
    length_penalty: float | None = Field(None, description="Exponential length penalty (default: 1.0)")

    # Prompt engineering
    initial_prompt: str | None = Field(None, description="Prompt for first transcription window")
    hotwords: str | None = Field(None, description="Comma-separated words to boost recognition")

    # Output control
    word_timestamps: bool | None = Field(None, description="Include word-level timestamps (default: true)")
    return_char_alignments: bool | None = Field(None, description="Include character-level alignments (default: false)")
    suppress_numerals: bool | None = Field(None, description="Spell out numbers instead of digits (default: false)")

    # Hallucination filtering
    compression_ratio_threshold: float | None = Field(None, description="Filter high compression segments (default: 2.4)")
    no_speech_threshold: float | None = Field(None, ge=0.0, le=1.0, description="Silence detection threshold (default: 0.6)")
    condition_on_previous_text: bool | None = Field(None, description="Use previous output as prompt (default: false)")

    # VAD parameters
    vad_onset: float | None = Field(None, ge=0.0, le=1.0, description="VAD speech onset threshold (default: 0.5)")
    vad_offset: float | None = Field(None, ge=0.0, le=1.0, description="VAD speech offset threshold (default: 0.363)")
    chunk_size: int | None = Field(None, ge=1, le=300, description="Maximum audio chunk duration in seconds (default: 30)")

    # Webhook callback
    webhook_url: HttpUrl | None = Field(None, description="URL to POST results when complete")
    webhook_auth_header: str | None = Field(None, description="Authorization header for webhook")


class TranscriptWord(BaseModel):
    """Word-level transcription data."""

    text: str
    start: int  # milliseconds
    end: int  # milliseconds
    confidence: float
    speaker: str | None = None


class TranscriptUtterance(BaseModel):
    """Speaker utterance (segment) data."""

    speaker: str
    text: str
    start: int  # milliseconds
    end: int  # milliseconds
    confidence: float
    words: list[TranscriptWord] | None = None


class Transcript(BaseModel):
    """Full transcript response."""

    id: str
    status: Literal["queued", "processing", "completed", "error"]
    audio_url: str | None = None
    language_code: str | None = None
    text: str | None = None
    words: list[TranscriptWord] | None = None
    utterances: list[TranscriptUtterance] | None = None
    confidence: float | None = None
    audio_duration: int | None = None  # milliseconds
    progress: float = 0.0  # 0.0 to 1.0
    error: str | None = None


class TranscriptListItem(BaseModel):
    """Transcript summary for list endpoint."""

    id: str
    status: str
    audio_url: str | None = None
    progress: float = 0.0
    created_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class Pagination(BaseModel):
    """Pagination info for list responses."""

    total: int
    limit: int
    offset: int


class TranscriptList(BaseModel):
    """Response for list transcripts endpoint."""

    transcripts: list[TranscriptListItem]
    pagination: Pagination


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class ReadyResponse(BaseModel):
    """Ready check response."""

    status: str
    gpu: str
    model: str
