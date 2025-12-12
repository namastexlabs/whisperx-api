"""SQLite database for transcript persistence."""

import json
from typing import Any

import aiosqlite

from murmurai_server.config import get_settings


async def init_db() -> None:
    """Initialize SQLite database and create tables."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id TEXT PRIMARY KEY,
                audio_url TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                language_code TEXT,
                speaker_labels INTEGER DEFAULT 0,
                speakers_expected INTEGER,
                text TEXT,
                words TEXT,
                utterances TEXT,
                confidence REAL,
                audio_duration INTEGER,
                error TEXT,
                progress REAL DEFAULT 0.0,
                webhook_url TEXT,
                webhook_auth_header TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        # Add progress column if missing (migration for existing DBs)
        try:
            await db.execute("ALTER TABLE transcripts ADD COLUMN progress REAL DEFAULT 0.0")
        except Exception:
            pass  # Column already exists
        try:
            await db.execute("ALTER TABLE transcripts ADD COLUMN webhook_url TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE transcripts ADD COLUMN webhook_auth_header TEXT")
        except Exception:
            pass
        await db.commit()


async def create_transcript(
    id: str,
    audio_url: str | None,
    language: str | None,
    speaker_labels: bool,
    speakers_expected: int | None,
    webhook_url: str | None = None,
    webhook_auth_header: str | None = None,
) -> dict[str, Any]:
    """Create a new transcript record."""
    settings = get_settings()

    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            """INSERT INTO transcripts
               (id, audio_url, language_code, speaker_labels, speakers_expected, webhook_url, webhook_auth_header)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                id,
                audio_url,
                language,
                int(speaker_labels),
                speakers_expected,
                webhook_url,
                webhook_auth_header,
            ),
        )
        await db.commit()

    return {
        "id": id,
        "status": "queued",
        "audio_url": audio_url,
        "language_code": language,
        "progress": 0.0,
    }


async def get_transcript(id: str) -> dict[str, Any] | None:
    """Get a transcript by ID."""
    settings = get_settings()

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM transcripts WHERE id = ?", (id,))
        row = await cursor.fetchone()

        if not row:
            return None

        result = dict(row)

        # Parse JSON fields
        if result.get("words"):
            result["words"] = json.loads(result["words"])
        if result.get("utterances"):
            result["utterances"] = json.loads(result["utterances"])

        # Convert boolean
        result["speaker_labels"] = bool(result.get("speaker_labels", 0))

        return result


async def update_transcript(id: str, **kwargs: Any) -> None:
    """Update transcript fields."""
    settings = get_settings()

    # Serialize JSON fields
    if "words" in kwargs and kwargs["words"] is not None:
        kwargs["words"] = json.dumps(kwargs["words"])
    if "utterances" in kwargs and kwargs["utterances"] is not None:
        kwargs["utterances"] = json.dumps(kwargs["utterances"])

    # Handle completed_at timestamp
    if kwargs.get("status") == "completed":
        kwargs["completed_at"] = "datetime('now')"

    # Build SET clause
    set_parts = []
    values = []
    for key, value in kwargs.items():
        if key == "completed_at" and value == "datetime('now')":
            set_parts.append(f"{key} = datetime('now')")
        else:
            set_parts.append(f"{key} = ?")
            values.append(value)

    values.append(id)
    set_clause = ", ".join(set_parts)

    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(f"UPDATE transcripts SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def list_transcripts(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """List transcripts with optional status filter and pagination.

    Returns:
        Tuple of (transcripts list, total count).
    """
    settings = get_settings()

    # Base WHERE clause
    where_clause = ""
    params: list[Any] = []
    if status:
        where_clause = " WHERE status = ?"
        params.append(status)

    # Get total count
    count_query = f"SELECT COUNT(*) FROM transcripts{where_clause}"

    # Get paginated results
    query = f"SELECT id, audio_url, status, progress, created_at, completed_at, error FROM transcripts{where_clause}"
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    query_params = params + [limit, offset]

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get total count
        cursor = await db.execute(count_query, params)
        row = await cursor.fetchone()
        total = row[0] if row else 0

        # Get transcripts
        cursor = await db.execute(query, query_params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def delete_transcript(id: str) -> bool:
    """Delete a transcript by ID. Returns True if deleted."""
    settings = get_settings()

    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute("DELETE FROM transcripts WHERE id = ?", (id,))
        await db.commit()
        return cursor.rowcount > 0
