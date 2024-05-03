import sqlite3
from src.api.database import get_db


def test_get_db():
    conn, cursor = get_db()
    assert isinstance(conn, sqlite3.Connection)
    assert isinstance(cursor, sqlite3.Cursor)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    assert cursor.fetchone()[0] == "users"

    conn.close()
