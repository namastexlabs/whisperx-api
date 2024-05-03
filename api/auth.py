import os
from api.config import MASTER_KEY, SECRET_KEY, TOKEN_EXPIRATION_DAYS
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
from .database import get_db
import sqlite3


security = HTTPBearer()
oauth2_scheme = HTTPBearer(scheme_name="JWT")


def create_jwt_token(data: dict):
    token_expiration = datetime.utcnow() + timedelta(days=TOKEN_EXPIRATION_DAYS)
    data["exp"] = token_expiration
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def decode_jwt_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Signature has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):
    token = credentials.credentials
    conn, cursor = get_db()
    cursor.execute("SELECT username, token_expiration FROM users WHERE token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        username, token_expiration_str = row
        if token_expiration_str:
            token_expiration = datetime.fromisoformat(token_expiration_str)
            if token_expiration > datetime.utcnow():
                return {"username": username}
    raise HTTPException(status_code=401, detail="Invalid or expired token")


def auth(username: str, password: str):
    conn, cursor = get_db()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and row[0] == password:
        token_expiration = datetime.utcnow() + timedelta(days=TOKEN_EXPIRATION_DAYS)
        token = create_jwt_token({"sub": username, "exp": token_expiration})
        cursor.execute("UPDATE users SET token = ?, token_expiration = ? WHERE username = ?", (token, token_expiration.isoformat(), username))
        conn.commit()
        conn.close()
        return {"access_token": token, "token_type": "bearer"}
    else:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")  
    
def create_user(username: str, password: str, master_key: str):
    if master_key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Not authorized")
    conn, cursor = get_db()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return {"detail": "User created successfully"}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")