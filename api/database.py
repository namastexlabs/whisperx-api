import sqlite3

def get_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, token TEXT, token_expiration DATETIME)"
    )
    conn.commit()
    return conn, cursor