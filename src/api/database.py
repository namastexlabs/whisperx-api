import os
import sqlite3


def get_db():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, "users.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT, token TEXT, token_expiration TEXT)"
    )
    return conn, cursor
