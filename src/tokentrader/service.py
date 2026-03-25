from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .engine import build_quote, execute
from .models import ExecuteResponse, QualityTier, TaskOrder


class TokenTraderService:
    def __init__(self, db_path: str = "tokentrader.db") -> None:
        self.db_path = db_path
        db_parent = Path(db_path).resolve().parent
        db_parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        salt_b64, digest_b64 = stored_hash.split(":", maxsplit=1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)

    def register_user(self, email: str, password: str, name: str) -> dict:
        email = email.strip().lower()
        name = name.strip()
        if "@" not in email or len(email) < 5:
            raise ValueError("邮箱格式不正确")
        if len(password) < 8:
            raise ValueError("密码至少 8 位")
        if len(name) < 2:
            raise ValueError("昵称至少 2 位")

        with self._connect() as conn:
            exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if exists:
                raise ValueError("邮箱已注册")

            created_at = self._utcnow().isoformat()
            cursor = conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email, name, self._hash_password(password), created_at),
            )
            user_id = cursor.lastrowid

        return {"id": user_id, "email": email, "name": name, "created_at": created_at}

    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row or not self._verify_password(password, row["password_hash"]):
                raise ValueError("邮箱或密码错误")

            token = secrets.token_urlsafe(24)
            created_at = self._utcnow()
            expires_at = created_at + timedelta(days=7)
            conn.execute(
                "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token, row["id"], expires_at.isoformat(), created_at.isoformat()),
            )

        return {
            "token": token,
            "user": {"id": row["id"], "email": row["email"], "name": row["name"]},
            "expires_at": expires_at.isoformat(),
        }

    def get_user_by_token(self, token: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.email, u.name, s.expires_at
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = ?
                """,
                (token,),
            ).fetchone()

            if not row:
                return None

            if datetime.fromisoformat(row["expires_at"]) < self._utcnow():
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return None

            return {"id": row["id"], "email": row["email"], "name": row["name"]}

    def build_quote_for_user(self, token: str, payload: dict) -> dict:
        user = self.get_user_by_token(token)
        if not user:
            raise PermissionError("未登录或会话失效")

        tier = QualityTier(payload.get("quality_tier", QualityTier.BALANCED.value))
        order = TaskOrder(
            task_type=payload.get("task_type", "general"),
            prompt_tokens=int(payload.get("prompt_tokens", 1000)),
            max_latency_ms=int(payload.get("max_latency_ms", 1500)),
            budget_credits=float(payload.get("budget_credits", 1.0)),
            quality_tier=tier,
        )

        quote = build_quote(order)
        return {
            "user": user,
            "order": asdict(quote.order),
            "candidates": [asdict(item) for item in quote.candidates],
        }

    def execute_for_user(self, token: str, payload: dict) -> dict:
        user = self.get_user_by_token(token)
        if not user:
            raise PermissionError("未登录或会话失效")

        tier = QualityTier(payload.get("quality_tier", QualityTier.BALANCED.value))
        order = TaskOrder(
            task_type=payload.get("task_type", "general"),
            prompt_tokens=int(payload.get("prompt_tokens", 1000)),
            max_latency_ms=int(payload.get("max_latency_ms", 1500)),
            budget_credits=float(payload.get("budget_credits", 1.0)),
            quality_tier=tier,
        )

        result: ExecuteResponse = execute(
            order=order,
            provider=str(payload.get("provider", "")),
            model=str(payload.get("model", "")),
        )
        return {"user": user, "result": asdict(result)}
