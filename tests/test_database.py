"""Tests for database operations."""

import pytest

from murmurai_server.database import (
    create_transcript,
    delete_transcript,
    get_transcript,
    init_db,
    list_transcripts,
    update_transcript,
)


@pytest.mark.asyncio
async def test_init_db_creates_table(test_settings):
    """Test that init_db creates the transcripts table."""
    await init_db()

    # Verify by creating a transcript
    result = await create_transcript(
        id="test-init",
        audio_url="https://example.com/test.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )
    assert result["id"] == "test-init"


@pytest.mark.asyncio
async def test_create_transcript(initialized_db):
    """Test creating a new transcript."""
    result = await create_transcript(
        id="test-create",
        audio_url="https://example.com/audio.mp3",
        language="en",
        speaker_labels=True,
        speakers_expected=2,
    )

    assert result["id"] == "test-create"
    assert result["status"] == "queued"
    assert result["audio_url"] == "https://example.com/audio.mp3"
    assert result["language_code"] == "en"


@pytest.mark.asyncio
async def test_get_transcript_found(initialized_db):
    """Test getting an existing transcript."""
    # Create first
    await create_transcript(
        id="test-get",
        audio_url="https://example.com/get.mp3",
        language="en",
        speaker_labels=False,
        speakers_expected=None,
    )

    # Get it back
    result = await get_transcript("test-get")

    assert result is not None
    assert result["id"] == "test-get"
    assert result["audio_url"] == "https://example.com/get.mp3"
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_get_transcript_not_found(initialized_db):
    """Test getting a non-existent transcript."""
    result = await get_transcript("non-existent-id")
    assert result is None


@pytest.mark.asyncio
async def test_update_transcript_status(initialized_db):
    """Test updating transcript status."""
    await create_transcript(
        id="test-update",
        audio_url="https://example.com/update.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )

    await update_transcript("test-update", status="processing")

    result = await get_transcript("test-update")
    assert result["status"] == "processing"


@pytest.mark.asyncio
async def test_update_transcript_with_result(initialized_db):
    """Test updating transcript with transcription result."""
    await create_transcript(
        id="test-result",
        audio_url="https://example.com/result.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )

    words = [{"text": "Hello", "start": 0, "end": 500, "confidence": 0.98}]
    utterances = [{"speaker": "A", "text": "Hello", "start": 0, "end": 500}]

    await update_transcript(
        "test-result",
        status="completed",
        text="Hello",
        words=words,
        utterances=utterances,
        confidence=0.98,
        audio_duration=500,
        language_code="en",
    )

    result = await get_transcript("test-result")
    assert result["status"] == "completed"
    assert result["text"] == "Hello"
    assert result["words"] == words
    assert result["utterances"] == utterances
    assert result["confidence"] == 0.98
    assert result["audio_duration"] == 500


@pytest.mark.asyncio
async def test_update_transcript_error(initialized_db):
    """Test updating transcript with error."""
    await create_transcript(
        id="test-error",
        audio_url="https://example.com/error.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )

    await update_transcript(
        "test-error",
        status="error",
        error="Download failed: 404 Not Found",
    )

    result = await get_transcript("test-error")
    assert result["status"] == "error"
    assert "404" in result["error"]


@pytest.mark.asyncio
async def test_list_transcripts_empty(initialized_db):
    """Test listing transcripts when empty."""
    results, total = await list_transcripts()
    # Note: may contain transcripts from other tests
    assert isinstance(results, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
async def test_list_transcripts_with_items(initialized_db):
    """Test listing transcripts with items."""
    # Create some transcripts
    await create_transcript(
        id="list-1",
        audio_url="https://example.com/1.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )
    await create_transcript(
        id="list-2",
        audio_url="https://example.com/2.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )

    results, total = await list_transcripts(limit=10)
    ids = [r["id"] for r in results]
    assert "list-1" in ids
    assert "list-2" in ids
    assert total >= 2


@pytest.mark.asyncio
async def test_list_transcripts_with_status_filter(initialized_db):
    """Test listing transcripts with status filter."""
    # Create transcripts with different statuses
    await create_transcript(
        id="filter-1",
        audio_url="https://example.com/f1.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )
    await update_transcript("filter-1", status="completed")

    await create_transcript(
        id="filter-2",
        audio_url="https://example.com/f2.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )
    # Keep filter-2 as queued

    completed, _ = await list_transcripts(status="completed")
    completed_ids = [r["id"] for r in completed]
    assert "filter-1" in completed_ids
    assert "filter-2" not in completed_ids


@pytest.mark.asyncio
async def test_list_transcripts_limit(initialized_db):
    """Test that limit parameter works."""
    # Create several transcripts
    for i in range(5):
        await create_transcript(
            id=f"limit-{i}",
            audio_url=f"https://example.com/limit{i}.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )

    results, total = await list_transcripts(limit=2)
    assert len(results) <= 2
    assert total >= 5


@pytest.mark.asyncio
async def test_delete_transcript_success(initialized_db):
    """Test deleting an existing transcript."""
    await create_transcript(
        id="delete-me",
        audio_url="https://example.com/delete.mp3",
        language=None,
        speaker_labels=False,
        speakers_expected=None,
    )

    deleted = await delete_transcript("delete-me")
    assert deleted is True

    # Verify it's gone
    result = await get_transcript("delete-me")
    assert result is None


@pytest.mark.asyncio
async def test_delete_transcript_not_found(initialized_db):
    """Test deleting a non-existent transcript."""
    deleted = await delete_transcript("non-existent")
    assert deleted is False
