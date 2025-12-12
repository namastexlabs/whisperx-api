"""Pydantic models for API request/response."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class TranscriptParams(BaseModel):
    """Request body for creating a transcript.

    Supports both URL and file upload (file handled separately in endpoint).
    All parameters use sensible defaults.
    """

    # Audio source (URL - file upload handled via multipart form)
    audio_url: HttpUrl | None = None

    # Language settings
    language_code: str | None = None

    # Speaker diarization
    speaker_labels: bool = Field(False, description="Enable speaker diarization")
    speakers_expected: int | None = Field(None, description="Expected number of speakers")
    min_speakers: int | None = Field(None, description="Minimum expected speakers")
    max_speakers: int | None = Field(None, description="Maximum expected speakers")
    diarize_model: str = Field(
        "pyannote/speaker-diarization-3.1",
        description="Diarization model (pyannote/speaker-diarization-3.1 or community-1)",
    )
    return_speaker_embeddings: bool = Field(
        False, description="Include speaker embedding vectors in response"
    )

    # Transcription task
    task: Literal["transcribe", "translate"] = Field(
        "transcribe", description="'transcribe' for same language, 'translate' to English"
    )

    # Prompt engineering
    initial_prompt: str | None = Field(None, description="Prompt for first transcription window")
    hotwords: str | None = Field(None, description="Comma-separated words to boost recognition")

    # Decoding parameters (defaults)
    temperature: float = Field(0.0, ge=0.0, le=1.0, description="Sampling temperature (0=greedy)")
    temperature_increment_on_fallback: float | None = Field(
        0.2, description="Temperature increase on decode failure (None to disable)"
    )
    beam_size: int = Field(5, ge=1, le=10, description="Beam search size")
    best_of: int = Field(5, ge=1, description="Number of sampling alternatives")
    patience: float = Field(1.0, ge=0.0, description="Beam search patience factor")
    length_penalty: float = Field(1.0, description="Exponential length penalty")
    suppress_tokens: str | None = Field(
        None, description="Comma-separated token IDs to suppress during decoding"
    )
    logprob_threshold: float | None = Field(
        -1.0, description="Log probability threshold for filtering low-confidence segments"
    )

    # Output control
    word_timestamps: bool = Field(False, description="Include word-level timestamps")
    return_char_alignments: bool = Field(False, description="Include character-level alignments")
    suppress_numerals: bool = Field(False, description="Spell out numbers instead of digits")
    interpolate_method: Literal["nearest", "linear", "ignore"] = Field(
        "nearest", description="Method for interpolating word boundaries"
    )

    # Hallucination filtering (defaults)
    compression_ratio_threshold: float = Field(2.4, description="Filter high compression segments")
    no_speech_threshold: float = Field(
        0.6, ge=0.0, le=1.0, description="Silence detection threshold"
    )
    condition_on_previous_text: bool = Field(False, description="Use previous output as prompt")

    # VAD parameters (defaults)
    vad_method: Literal["pyannote", "silero"] = Field(
        "pyannote", description="VAD algorithm: pyannote (default) or silero (lighter)"
    )
    vad_onset: float = Field(0.5, ge=0.0, le=1.0, description="VAD speech onset threshold")
    vad_offset: float = Field(0.363, ge=0.0, le=1.0, description="VAD speech offset threshold")
    chunk_size: int = Field(30, ge=1, le=300, description="Max audio chunk duration in seconds")

    # Subtitle/segment formatting
    segment_resolution: Literal["sentence", "chunk"] = Field(
        "sentence", description="Segment splitting strategy: sentence or chunk"
    )
    max_line_width: int | None = Field(None, description="Max characters per subtitle line")
    max_line_count: int | None = Field(None, description="Max lines per subtitle segment")
    highlight_words: bool = Field(False, description="Highlight current word in subtitles")

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
