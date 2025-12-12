"""Tests for FastAPI server endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from murmurai_server.database import create_transcript, update_transcript


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, async_client: AsyncClient):
        """Test /health endpoint returns ok."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, async_client: AsyncClient):
        """Test /health doesn't require authentication."""
        response = await async_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ready_with_gpu(
        self, async_client: AsyncClient, mock_gpu_available, test_settings
    ):
        """Test /ready endpoint when GPU is available."""
        response = await async_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "gpu" in data
        assert data["model"] == test_settings.model

    @pytest.mark.asyncio
    async def test_ready_without_gpu(self, async_client: AsyncClient):
        """Test /ready endpoint when GPU is not available."""
        with patch("torch.cuda.is_available", return_value=False):
            response = await async_client.get("/ready")
            assert response.status_code == 503


class TestTranscriptEndpoints:
    """Tests for transcript API endpoints."""

    @pytest.mark.asyncio
    async def test_submit_transcript_with_url(
        self, async_client: AsyncClient, auth_headers: dict, tmp_path: Path
    ):
        """Test POST /v1/transcript with URL creates a new job."""
        # Create a temp file for the mock
        test_audio = tmp_path / "test.mp3"
        test_audio.touch()

        with patch("murmurai_server.server.download_audio", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = test_audio

            response = await async_client.post(
                "/v1/transcript",
                headers=auth_headers,
                data={"audio_url": "https://example.com/test.mp3"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_submit_transcript_with_options(
        self, async_client: AsyncClient, auth_headers: dict, tmp_path: Path
    ):
        """Test POST /v1/transcript with all options."""
        # Create a temp file for the mock
        test_audio = tmp_path / "test.mp3"
        test_audio.touch()

        with patch("murmurai_server.server.download_audio", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = test_audio

            response = await async_client.post(
                "/v1/transcript",
                headers=auth_headers,
                data={
                    "audio_url": "https://example.com/test.mp3",
                    "language_code": "en",
                    "speaker_labels": "true",
                    "speakers_expected": "2",
                    "task": "transcribe",
                    "temperature": "0.0",
                    "beam_size": "5",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["language_code"] == "en"

    @pytest.mark.asyncio
    async def test_submit_transcript_no_audio(self, async_client: AsyncClient, auth_headers: dict):
        """Test POST /v1/transcript without audio fails."""
        response = await async_client.post(
            "/v1/transcript",
            headers=auth_headers,
            data={},
        )
        assert response.status_code == 400
        assert (
            "audio_url" in response.json()["detail"].lower()
            or "file" in response.json()["detail"].lower()
        )

    @pytest.mark.asyncio
    async def test_submit_transcript_no_auth(self, async_client: AsyncClient):
        """Test POST /v1/transcript without auth fails."""
        response = await async_client.post(
            "/v1/transcript",
            data={"audio_url": "https://example.com/test.mp3"},
        )
        assert response.status_code == 401  # Missing Authorization header

    @pytest.mark.asyncio
    async def test_submit_transcript_invalid_auth(self, async_client: AsyncClient):
        """Test POST /v1/transcript with invalid auth fails."""
        response = await async_client.post(
            "/v1/transcript",
            headers={"Authorization": "wrong-key"},
            data={"audio_url": "https://example.com/test.mp3"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_transcript(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id} returns transcript."""
        # Create a transcript directly
        await create_transcript(
            id="get-test-id",
            audio_url="https://example.com/get.mp3",
            language="en",
            speaker_labels=False,
            speakers_expected=None,
        )

        response = await async_client.get(
            "/v1/transcript/get-test-id",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "get-test-id"
        assert data["audio_url"] == "https://example.com/get.mp3"

    @pytest.mark.asyncio
    async def test_get_transcript_not_found(self, async_client: AsyncClient, auth_headers: dict):
        """Test GET /v1/transcript/{id} returns 404 for missing."""
        response = await async_client.get(
            "/v1/transcript/non-existent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_transcripts(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript returns list with pagination."""
        await create_transcript(
            id="list-test-1",
            audio_url="https://example.com/list1.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )

        response = await async_client.get(
            "/v1/transcript",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "transcripts" in data
        assert isinstance(data["transcripts"], list)
        assert "pagination" in data
        assert "total" in data["pagination"]
        assert "limit" in data["pagination"]
        assert "offset" in data["pagination"]

    @pytest.mark.asyncio
    async def test_list_transcripts_with_filter(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript with status filter."""
        response = await async_client.get(
            "/v1/transcript",
            headers=auth_headers,
            params={"status": "queued", "limit": 10, "offset": 0},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_transcript(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test DELETE /v1/transcript/{id} deletes transcript."""
        await create_transcript(
            id="delete-test-id",
            audio_url="https://example.com/delete.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )

        response = await async_client.delete(
            "/v1/transcript/delete-test-id",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "delete-test-id"
        assert data["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_transcript_not_found(self, async_client: AsyncClient, auth_headers: dict):
        """Test DELETE /v1/transcript/{id} returns 404 for missing."""
        response = await async_client.delete(
            "/v1/transcript/non-existent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestSubtitleEndpoints:
    """Tests for subtitle export endpoints."""

    @pytest.mark.asyncio
    async def test_get_srt_completed(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id}/srt returns SRT."""
        await create_transcript(
            id="srt-test-id",
            audio_url="https://example.com/srt.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )
        await update_transcript(
            "srt-test-id",
            status="completed",
            text="Hello World",
            utterances=[{"speaker": "A", "text": "Hello World", "start": 0, "end": 1000}],
        )

        response = await async_client.get(
            "/v1/transcript/srt-test-id/srt",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/srt" in response.headers["content-type"]
        assert "Hello World" in response.text

    @pytest.mark.asyncio
    async def test_get_srt_not_ready(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id}/srt returns 400 if not completed."""
        await create_transcript(
            id="srt-pending-id",
            audio_url="https://example.com/srt-pending.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )

        response = await async_client.get(
            "/v1/transcript/srt-pending-id/srt",
            headers=auth_headers,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_vtt_completed(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id}/vtt returns VTT."""
        await create_transcript(
            id="vtt-test-id",
            audio_url="https://example.com/vtt.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )
        await update_transcript(
            "vtt-test-id",
            status="completed",
            text="Test Text",
            utterances=[{"speaker": "A", "text": "Test Text", "start": 0, "end": 500}],
        )

        response = await async_client.get(
            "/v1/transcript/vtt-test-id/vtt",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/vtt" in response.headers["content-type"]
        assert "WEBVTT" in response.text
        assert "Test Text" in response.text

    @pytest.mark.asyncio
    async def test_get_txt_completed(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id}/txt returns plain text."""
        await create_transcript(
            id="txt-test-id",
            audio_url="https://example.com/txt.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )
        await update_transcript(
            "txt-test-id",
            status="completed",
            text="Plain text content",
        )

        response = await async_client.get(
            "/v1/transcript/txt-test-id/txt",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "Plain text content" in response.text

    @pytest.mark.asyncio
    async def test_get_json_completed(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id}/json returns JSON download."""
        await create_transcript(
            id="json-test-id",
            audio_url="https://example.com/json.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )
        await update_transcript(
            "json-test-id",
            status="completed",
            text="JSON test",
        )

        response = await async_client.get(
            "/v1/transcript/json-test-id/json",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_get_words_completed(
        self, async_client: AsyncClient, auth_headers: dict, initialized_db
    ):
        """Test GET /v1/transcript/{id}/words returns word timestamps."""
        await create_transcript(
            id="words-test-id",
            audio_url="https://example.com/words.mp3",
            language=None,
            speaker_labels=False,
            speakers_expected=None,
        )
        await update_transcript(
            "words-test-id",
            status="completed",
            text="Word test",
            words=[{"text": "Word", "start": 0, "end": 500, "confidence": 0.98}],
        )

        response = await async_client.get(
            "/v1/transcript/words-test-id/words",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "words" in data
        assert len(data["words"]) == 1
