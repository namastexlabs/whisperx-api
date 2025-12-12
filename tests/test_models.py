"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from murmurai_server.models import (
    HealthResponse,
    Pagination,
    ReadyResponse,
    Transcript,
    TranscriptList,
    TranscriptListItem,
    TranscriptParams,
    TranscriptUtterance,
    TranscriptWord,
)


class TestTranscriptParams:
    """Tests for TranscriptParams model."""

    def test_valid_params_with_url(self):
        """Test valid transcript params with URL."""
        params = TranscriptParams(
            audio_url="https://example.com/audio.mp3",
            language_code="en",
            speaker_labels=True,
            speakers_expected=2,
        )
        assert str(params.audio_url) == "https://example.com/audio.mp3"
        assert params.language_code == "en"
        assert params.speaker_labels is True
        assert params.speakers_expected == 2

    def test_minimal_params(self):
        """Test params with MurmurAI defaults (for file upload case)."""
        params = TranscriptParams()
        assert params.audio_url is None
        assert params.language_code is None
        assert params.speaker_labels is False
        assert params.speakers_expected is None
        assert params.task == "transcribe"
        assert params.temperature == 0.0
        assert params.beam_size == 5

    def test_all_transcription_params(self):
        """Test all murmurai transcription parameters."""
        params = TranscriptParams(
            audio_url="https://example.com/audio.mp3",
            language_code="en",
            speaker_labels=True,
            speakers_expected=2,
            min_speakers=1,
            max_speakers=3,
            task="translate",
            temperature=0.5,
            beam_size=8,
            best_of=3,
            patience=1.5,
            length_penalty=0.8,
            initial_prompt="This is a meeting.",
            hotwords="MurmurAI,transcription",
            word_timestamps=True,
            return_char_alignments=True,
            suppress_numerals=True,
            compression_ratio_threshold=2.0,
            no_speech_threshold=0.5,
            condition_on_previous_text=True,
            vad_onset=0.6,
            vad_offset=0.4,
            chunk_size=20,
            webhook_url="https://example.com/webhook",
            webhook_auth_header="Bearer token",
        )
        assert params.task == "translate"
        assert params.temperature == 0.5
        assert params.initial_prompt == "This is a meeting."
        assert params.suppress_numerals is True
        assert params.vad_onset == 0.6

    def test_invalid_url(self):
        """Test that invalid URL raises error."""
        with pytest.raises(ValidationError):
            TranscriptParams(audio_url="not-a-url")

    def test_http_url_allowed(self):
        """Test that HTTP URLs are allowed."""
        params = TranscriptParams(audio_url="http://example.com/audio.mp3")
        assert "http://" in str(params.audio_url)

    def test_invalid_task(self):
        """Test that invalid task raises error."""
        with pytest.raises(ValidationError):
            TranscriptParams(task="invalid")

    def test_temperature_bounds(self):
        """Test temperature validation bounds."""
        params = TranscriptParams(temperature=0.5)
        assert params.temperature == 0.5

        with pytest.raises(ValidationError):
            TranscriptParams(temperature=1.5)

        with pytest.raises(ValidationError):
            TranscriptParams(temperature=-0.1)


class TestTranscriptWord:
    """Tests for TranscriptWord model."""

    def test_word_with_speaker(self):
        """Test word with speaker."""
        word = TranscriptWord(
            text="Hello",
            start=0,
            end=500,
            confidence=0.98,
            speaker="A",
        )
        assert word.text == "Hello"
        assert word.start == 0
        assert word.end == 500
        assert word.confidence == 0.98
        assert word.speaker == "A"

    def test_word_without_speaker(self):
        """Test word without speaker."""
        word = TranscriptWord(
            text="World",
            start=500,
            end=1000,
            confidence=0.95,
        )
        assert word.speaker is None


class TestTranscriptUtterance:
    """Tests for TranscriptUtterance model."""

    def test_utterance_with_words(self):
        """Test utterance with embedded words."""
        words = [
            TranscriptWord(text="Hello", start=0, end=500, confidence=0.98),
            TranscriptWord(text="World", start=500, end=1000, confidence=0.95),
        ]
        utterance = TranscriptUtterance(
            speaker="A",
            text="Hello World",
            start=0,
            end=1000,
            confidence=0.96,
            words=words,
        )
        assert len(utterance.words) == 2
        assert utterance.words[0].text == "Hello"

    def test_utterance_without_words(self):
        """Test utterance without words list."""
        utterance = TranscriptUtterance(
            speaker="B",
            text="Test",
            start=0,
            end=500,
            confidence=0.9,
        )
        assert utterance.words is None


class TestTranscript:
    """Tests for Transcript model."""

    def test_queued_transcript(self):
        """Test transcript in queued status."""
        transcript = Transcript(
            id="test-id",
            status="queued",
            audio_url="https://example.com/audio.mp3",
        )
        assert transcript.status == "queued"
        assert transcript.text is None
        assert transcript.words is None
        assert transcript.progress == 0.0

    def test_processing_transcript_with_progress(self):
        """Test processing transcript with progress."""
        transcript = Transcript(
            id="test-id",
            status="processing",
            progress=0.5,
        )
        assert transcript.status == "processing"
        assert transcript.progress == 0.5

    def test_completed_transcript(self):
        """Test completed transcript with all fields."""
        transcript = Transcript(
            id="test-id",
            status="completed",
            audio_url="https://example.com/audio.mp3",
            language_code="en",
            text="Hello World",
            confidence=0.96,
            audio_duration=1000,
            progress=1.0,
        )
        assert transcript.status == "completed"
        assert transcript.text == "Hello World"
        assert transcript.progress == 1.0

    def test_error_transcript(self):
        """Test transcript with error."""
        transcript = Transcript(
            id="test-id",
            status="error",
            audio_url="https://example.com/audio.mp3",
            error="Download failed",
        )
        assert transcript.status == "error"
        assert transcript.error == "Download failed"

    def test_invalid_status(self):
        """Test that invalid status raises error."""
        with pytest.raises(ValidationError):
            Transcript(
                id="test-id",
                status="invalid",
                audio_url="https://example.com/audio.mp3",
            )


class TestTranscriptList:
    """Tests for TranscriptList model."""

    def test_empty_list(self):
        """Test empty transcript list with pagination."""
        result = TranscriptList(
            transcripts=[],
            pagination=Pagination(total=0, limit=100, offset=0),
        )
        assert len(result.transcripts) == 0
        assert result.pagination.total == 0

    def test_list_with_items(self):
        """Test transcript list with items and pagination."""
        items = [
            TranscriptListItem(
                id="id-1",
                status="completed",
                audio_url="https://example.com/1.mp3",
                progress=1.0,
            ),
            TranscriptListItem(
                id="id-2",
                status="queued",
                audio_url="https://example.com/2.mp3",
                progress=0.0,
            ),
        ]
        result = TranscriptList(
            transcripts=items,
            pagination=Pagination(total=100, limit=10, offset=0),
        )
        assert len(result.transcripts) == 2
        assert result.pagination.total == 100
        assert result.pagination.limit == 10
        assert result.pagination.offset == 0


class TestPagination:
    """Tests for Pagination model."""

    def test_pagination(self):
        """Test pagination model."""
        pagination = Pagination(total=500, limit=100, offset=200)
        assert pagination.total == 500
        assert pagination.limit == 100
        assert pagination.offset == 200


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response(self):
        """Test health response."""
        response = HealthResponse(status="ok")
        assert response.status == "ok"


class TestReadyResponse:
    """Tests for ReadyResponse model."""

    def test_ready_response(self):
        """Test ready response."""
        response = ReadyResponse(
            status="ready",
            gpu="NVIDIA RTX 4090",
            model="large-v3-turbo",
        )
        assert response.status == "ready"
        assert "NVIDIA" in response.gpu
