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

from .engine import DEFAULT_OFFERS, build_quote, execute
from .models import QualityTier, TaskOrder

WELCOME_MANA = 240
THREAD_KINDS = {"thread", "forum"}


class TokenTraderService:
    def __init__(self, db_path: str = "tokentrader.db") -> None:
        self.db_path = db_path
        Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    bounty_mana INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(author_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(id),
                    FOREIGN KEY(author_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER,
                    creator_id INTEGER NOT NULL,
                    assignee_id INTEGER,
                    title TEXT NOT NULL,
                    brief TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reward_mana INTEGER NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    max_latency_ms INTEGER NOT NULL,
                    budget_credits REAL NOT NULL,
                    quality_tier TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    deliverable TEXT,
                    external_ref TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY(thread_id) REFERENCES threads(id),
                    FOREIGN KEY(creator_id) REFERENCES users(id),
                    FOREIGN KEY(assignee_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS mana_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    reference_type TEXT NOT NULL,
                    reference_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
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

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _normalize_name(name: str, email: str) -> str:
        cleaned = name.strip()
        if len(cleaned) >= 2:
            return cleaned
        local = email.split("@", maxsplit=1)[0].replace(".", " ").replace("_", " ").strip()
        local = " ".join(part for part in local.split() if part)
        if len(local) >= 2:
            return local.title()
        return "Lobster"

    def _validate_credentials(self, email: str, password: str) -> tuple[str, str]:
        normalized_email = self._normalize_email(email)
        if "@" not in normalized_email or len(normalized_email) < 5:
            raise ValueError("邮箱格式不正确")
        if len(password) < 8:
            raise ValueError("密码至少 8 位")
        return normalized_email, password

    def _get_balance(self, conn: sqlite3.Connection, user_id: int) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) AS balance FROM mana_ledger WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return int(row["balance"]) if row else 0

    def _add_ledger_entry(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        delta: int,
        reason: str,
        reference_type: str,
        reference_id: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO mana_ledger (user_id, delta, reason, reference_type, reference_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, delta, reason, reference_type, reference_id, self._utcnow().isoformat()),
        )

    def _serialize_user(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "created_at": row["created_at"],
            "mana_balance": self._get_balance(conn, int(row["id"])),
        }

    def _create_session(self, conn: sqlite3.Connection, user_id: int) -> tuple[str, str]:
        token = secrets.token_urlsafe(24)
        created_at = self._utcnow()
        expires_at = created_at + timedelta(days=7)
        conn.execute(
            """
            INSERT INTO sessions (token, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, expires_at.isoformat(), created_at.isoformat()),
        )
        return token, expires_at.isoformat()

    def _create_user(self, conn: sqlite3.Connection, email: str, password: str, name: str) -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        normalized_name = self._normalize_name(name, normalized_email)
        created_at = self._utcnow().isoformat()
        cur = conn.execute(
            """
            INSERT INTO users (email, name, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (normalized_email, normalized_name, self._hash_password(normalized_password), created_at),
        )
        user_id = int(cur.lastrowid)
        self._add_ledger_entry(conn, user_id, WELCOME_MANA, "welcome_grant", "user", user_id)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._serialize_user(conn, row)

    def _get_session_user(self, conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT u.*, s.expires_at
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
        return row

    def _require_user(self, conn: sqlite3.Connection, token: str) -> dict:
        row = self._get_session_user(conn, token)
        if not row:
            raise PermissionError("未登录或会话失效")
        return self._serialize_user(conn, row)

    def _task_order_from_payload(self, payload: dict) -> TaskOrder:
        tier = QualityTier(str(payload.get("quality_tier", QualityTier.BALANCED.value)))
        return TaskOrder(
            task_type=str(payload.get("task_type", "general")).strip() or "general",
            prompt_tokens=int(payload.get("prompt_tokens", 1000)),
            max_latency_ms=int(payload.get("max_latency_ms", 1600)),
            budget_credits=float(payload.get("budget_credits", 1.0)),
            quality_tier=tier,
        )

    def _serialize_post(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "body": row["body"],
            "created_at": row["created_at"],
            "author": {
                "id": row["author_id"],
                "name": row["author_name"],
            },
        }

    def _serialize_thread_summary(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "title": row["title"],
            "body": row["body"],
            "bounty_mana": row["bounty_mana"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "reply_count": row["reply_count"],
            "author": {
                "id": row["author_id"],
                "name": row["author_name"],
            },
        }

    def _load_thread_detail(self, conn: sqlite3.Connection, thread_id: int) -> dict | None:
        thread_row = conn.execute(
            """
            SELECT
                t.*,
                u.name AS author_name,
                (
                    SELECT COUNT(*)
                    FROM posts p
                    WHERE p.thread_id = t.id
                ) AS reply_count
            FROM threads t
            JOIN users u ON u.id = t.author_id
            WHERE t.id = ?
            """,
            (thread_id,),
        ).fetchone()
        if not thread_row:
            return None
        posts = conn.execute(
            """
            SELECT p.*, u.name AS author_name
            FROM posts p
            JOIN users u ON u.id = p.author_id
            WHERE p.thread_id = ?
            ORDER BY p.created_at ASC
            """,
            (thread_id,),
        ).fetchall()
        return {
            **self._serialize_thread_summary(thread_row),
            "posts": [self._serialize_post(post) for post in posts],
        }

    def _serialize_task(self, row: sqlite3.Row, current_user_id: int) -> dict:
        route = None
        if row["provider"] and row["model"]:
            route = {
                "provider": row["provider"],
                "model": row["model"],
            }
        return {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "title": row["title"],
            "brief": row["brief"],
            "status": row["status"],
            "reward_mana": row["reward_mana"],
            "prompt_tokens": row["prompt_tokens"],
            "max_latency_ms": row["max_latency_ms"],
            "budget_credits": row["budget_credits"],
            "quality_tier": row["quality_tier"],
            "deliverable": row["deliverable"],
            "external_ref": row["external_ref"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
            "route": route,
            "creator": {
                "id": row["creator_id"],
                "name": row["creator_name"],
            },
            "assignee": None
            if row["assignee_id"] is None
            else {
                "id": row["assignee_id"],
                "name": row["assignee_name"],
            },
            "is_mine": int(row["creator_id"]) == current_user_id,
            "can_claim": row["status"] == "open",
            "can_complete": row["status"] == "in_progress" and row["assignee_id"] == current_user_id,
        }

    def _load_tasks(self, conn: sqlite3.Connection, current_user_id: int) -> list[dict]:
        rows = conn.execute(
            """
            SELECT
                t.*,
                creator.name AS creator_name,
                assignee.name AS assignee_name
            FROM tasks t
            JOIN users creator ON creator.id = t.creator_id
            LEFT JOIN users assignee ON assignee.id = t.assignee_id
            ORDER BY
                CASE t.status
                    WHEN 'open' THEN 0
                    WHEN 'in_progress' THEN 1
                    ELSE 2
                END,
                t.updated_at DESC
            LIMIT 18
            """
        ).fetchall()
        return [self._serialize_task(row, current_user_id) for row in rows]

    def _leaderboard(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        leaderboard = [self._serialize_user(conn, row) for row in rows]
        leaderboard.sort(key=lambda item: item["mana_balance"], reverse=True)
        return leaderboard[:8]

    def _stats(self, conn: sqlite3.Connection) -> dict:
        thread_count = conn.execute("SELECT COUNT(*) AS c FROM threads").fetchone()["c"]
        active_tasks = conn.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE status IN ('open', 'in_progress')"
        ).fetchone()["c"]
        completed_tasks = conn.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE status = 'done'"
        ).fetchone()["c"]
        locked_mana = conn.execute(
            "SELECT COALESCE(SUM(reward_mana), 0) AS c FROM tasks WHERE status IN ('open', 'in_progress')"
        ).fetchone()["c"]
        positive_mana = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) AS c FROM mana_ledger WHERE delta > 0"
        ).fetchone()["c"]
        return {
            "thread_count": int(thread_count),
            "active_tasks": int(active_tasks),
            "completed_tasks": int(completed_tasks),
            "locked_mana": int(locked_mana),
            "issued_mana": int(positive_mana),
        }

    def auth(self, email: str, password: str, name: str = "") -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
            created = False
            if row:
                if not self._verify_password(normalized_password, row["password_hash"]):
                    raise ValueError("邮箱或密码错误")
                user = self._serialize_user(conn, row)
            else:
                user = self._create_user(conn, normalized_email, normalized_password, name)
                created = True
            token, expires_at = self._create_session(conn, int(user["id"]))
        return {
            "token": token,
            "expires_at": expires_at,
            "created": created,
            "user": user,
        }

    def register_user(self, email: str, password: str, name: str) -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        if len(name.strip()) < 2:
            raise ValueError("昵称至少 2 位")
        with self._connect() as conn:
            if conn.execute("SELECT id FROM users WHERE email = ?", (normalized_email,)).fetchone():
                raise ValueError("邮箱已注册")
            return self._create_user(conn, normalized_email, normalized_password, name)

    def login(self, email: str, password: str) -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
            if not row or not self._verify_password(normalized_password, row["password_hash"]):
                raise ValueError("邮箱或密码错误")
            token, expires_at = self._create_session(conn, int(row["id"]))
            user = self._serialize_user(conn, row)
        return {"token": token, "user": user, "expires_at": expires_at}

    def get_user_by_token(self, token: str) -> dict | None:
        with self._connect() as conn:
            row = self._get_session_user(conn, token)
            if not row:
                return None
            return self._serialize_user(conn, row)

    def get_dashboard(self, token: str, thread_id: int | None = None) -> dict:
        with self._connect() as conn:
            user = self._require_user(conn, token)
            thread_rows = conn.execute(
                """
                SELECT
                    t.*,
                    u.name AS author_name,
                    (
                        SELECT COUNT(*)
                        FROM posts p
                        WHERE p.thread_id = t.id
                    ) AS reply_count
                FROM threads t
                JOIN users u ON u.id = t.author_id
                ORDER BY t.updated_at DESC
                LIMIT 18
                """
            ).fetchall()
            threads = [self._serialize_thread_summary(row) for row in thread_rows]
            selected_thread_id = thread_id or (threads[0]["id"] if threads else None)
            selected_thread = (
                self._load_thread_detail(conn, int(selected_thread_id))
                if selected_thread_id is not None
                else None
            )
            ledger_rows = conn.execute(
                """
                SELECT id, delta, reason, reference_type, reference_id, created_at
                FROM mana_ledger
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (user["id"],),
            ).fetchall()
            return {
                "user": user,
                "stats": self._stats(conn),
                "threads": threads,
                "selected_thread": selected_thread,
                "tasks": self._load_tasks(conn, int(user["id"])),
                "ledger": [
                    {
                        "id": row["id"],
                        "delta": row["delta"],
                        "reason": row["reason"],
                        "reference_type": row["reference_type"],
                        "reference_id": row["reference_id"],
                        "created_at": row["created_at"],
                    }
                    for row in ledger_rows
                ],
                "leaderboard": self._leaderboard(conn),
                "market": [
                    {
                        "provider": offer.provider,
                        "model": offer.model,
                        "price_per_1k_tokens": offer.price_per_1k_tokens,
                        "quality_score": offer.quality_score,
                        "reliability_score": offer.reliability_score,
                        "avg_latency_ms": offer.avg_latency_ms,
                        "available_tokens": offer.available_tokens,
                    }
                    for offer in DEFAULT_OFFERS
                ],
            }

    def create_thread(self, token: str, payload: dict) -> dict:
        title = str(payload.get("title", "")).strip()
        body = str(payload.get("body", "")).strip()
        kind = str(payload.get("kind", "thread")).strip().lower()
        if kind not in THREAD_KINDS:
            raise ValueError("讨论类型不正确")
        if len(title) < 4:
            raise ValueError("标题至少 4 个字符")
        if len(body) < 12:
            raise ValueError("内容至少 12 个字符")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            now = self._utcnow().isoformat()
            cur = conn.execute(
                """
                INSERT INTO threads (author_id, kind, title, body, bounty_mana, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"], kind, title, body, 0, now, now),
            )
            thread_id = int(cur.lastrowid)
            thread = self._load_thread_detail(conn, thread_id)
        return {"thread": thread}

    def create_post(self, token: str, payload: dict) -> dict:
        thread_id = int(payload.get("thread_id", 0))
        body = str(payload.get("body", "")).strip()
        if thread_id <= 0:
            raise ValueError("缺少 thread_id")
        if len(body) < 3:
            raise ValueError("回复至少 3 个字符")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            thread = conn.execute("SELECT id FROM threads WHERE id = ?", (thread_id,)).fetchone()
            if not thread:
                raise ValueError("讨论不存在")
            now = self._utcnow().isoformat()
            conn.execute(
                """
                INSERT INTO posts (thread_id, author_id, body, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (thread_id, user["id"], body, now),
            )
            conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, thread_id))
            detail = self._load_thread_detail(conn, thread_id)
        return {"thread": detail}

    def create_task(self, token: str, payload: dict) -> dict:
        title = str(payload.get("title", "")).strip()
        brief = str(payload.get("brief", "")).strip()
        reward_mana = int(payload.get("reward_mana", 32))
        create_thread = bool(payload.get("create_thread", True))
        if len(title) < 4:
            raise ValueError("任务标题至少 4 个字符")
        if len(brief) < 12:
            raise ValueError("任务说明至少 12 个字符")
        if reward_mana < 5:
            raise ValueError("奖励至少 5 mana")
        order = self._task_order_from_payload(payload)
        quote = build_quote(order)
        preferred = quote.candidates[0] if quote.candidates else None
        with self._connect() as conn:
            user = self._require_user(conn, token)
            if self._get_balance(conn, int(user["id"])) < reward_mana:
                raise ValueError("mana 余额不足，无法挂出赏金")
            now = self._utcnow().isoformat()
            thread_id = None
            if create_thread:
                thread_cur = conn.execute(
                    """
                    INSERT INTO threads (author_id, kind, title, body, bounty_mana, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user["id"], "forum", title, brief, reward_mana, now, now),
                )
                thread_id = int(thread_cur.lastrowid)
            cur = conn.execute(
                """
                INSERT INTO tasks (
                    thread_id,
                    creator_id,
                    assignee_id,
                    title,
                    brief,
                    status,
                    reward_mana,
                    prompt_tokens,
                    max_latency_ms,
                    budget_credits,
                    quality_tier,
                    provider,
                    model,
                    deliverable,
                    external_ref,
                    created_at,
                    updated_at,
                    completed_at
                )
                VALUES (?, ?, NULL, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL)
                """,
                (
                    thread_id,
                    user["id"],
                    title,
                    brief,
                    reward_mana,
                    order.prompt_tokens,
                    order.max_latency_ms,
                    order.budget_credits,
                    order.quality_tier.value,
                    preferred.provider if preferred else None,
                    preferred.model if preferred else None,
                    now,
                    now,
                ),
            )
            task_id = int(cur.lastrowid)
            self._add_ledger_entry(conn, int(user["id"]), -reward_mana, "task_bounty_locked", "task", task_id)
            row = conn.execute(
                """
                SELECT
                    t.*,
                    creator.name AS creator_name,
                    assignee.name AS assignee_name
                FROM tasks t
                JOIN users creator ON creator.id = t.creator_id
                LEFT JOIN users assignee ON assignee.id = t.assignee_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
        return {
            "task": self._serialize_task(row, int(user["id"])),
            "quote_candidates": [asdict(item) for item in quote.candidates[:3]],
        }

    def claim_task(self, token: str, payload: dict) -> dict:
        task_id = int(payload.get("task_id", 0))
        if task_id <= 0:
            raise ValueError("缺少 task_id")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            row = conn.execute(
                """
                SELECT
                    t.*,
                    creator.name AS creator_name,
                    assignee.name AS assignee_name
                FROM tasks t
                JOIN users creator ON creator.id = t.creator_id
                LEFT JOIN users assignee ON assignee.id = t.assignee_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
            if not row:
                raise ValueError("任务不存在")
            if row["status"] != "open":
                raise ValueError("任务当前不可认领")
            now = self._utcnow().isoformat()
            conn.execute(
                "UPDATE tasks SET assignee_id = ?, status = 'in_progress', updated_at = ? WHERE id = ?",
                (user["id"], now, task_id),
            )
            updated = conn.execute(
                """
                SELECT
                    t.*,
                    creator.name AS creator_name,
                    assignee.name AS assignee_name
                FROM tasks t
                JOIN users creator ON creator.id = t.creator_id
                LEFT JOIN users assignee ON assignee.id = t.assignee_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
        return {"task": self._serialize_task(updated, int(user["id"]))}

    def complete_task(self, token: str, payload: dict) -> dict:
        task_id = int(payload.get("task_id", 0))
        deliverable = str(payload.get("deliverable", "")).strip()
        external_ref = str(payload.get("external_ref", "")).strip()
        if task_id <= 0:
            raise ValueError("缺少 task_id")
        if len(deliverable) < 10:
            raise ValueError("交付结果至少 10 个字符")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            row = conn.execute(
                """
                SELECT
                    t.*,
                    creator.name AS creator_name,
                    assignee.name AS assignee_name
                FROM tasks t
                JOIN users creator ON creator.id = t.creator_id
                LEFT JOIN users assignee ON assignee.id = t.assignee_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
            if not row:
                raise ValueError("任务不存在")
            if row["status"] != "in_progress":
                raise ValueError("任务尚未进入执行中")
            if row["assignee_id"] != user["id"]:
                raise PermissionError("只有认领者可以完成任务")
            route_provider = str(payload.get("provider") or row["provider"] or "").strip()
            route_model = str(payload.get("model") or row["model"] or "").strip()
            route_result = None
            if route_provider and route_model:
                order = TaskOrder(
                    task_type="delegated_task",
                    prompt_tokens=int(row["prompt_tokens"]),
                    max_latency_ms=int(row["max_latency_ms"]),
                    budget_credits=float(row["budget_credits"]),
                    quality_tier=QualityTier(str(row["quality_tier"])),
                )
                route_result = asdict(execute(order, route_provider, route_model))
            now = self._utcnow().isoformat()
            conn.execute(
                """
                UPDATE tasks
                SET
                    status = 'done',
                    provider = ?,
                    model = ?,
                    deliverable = ?,
                    external_ref = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (route_provider or None, route_model or None, deliverable, external_ref or None, now, now, task_id),
            )
            self._add_ledger_entry(conn, int(user["id"]), int(row["reward_mana"]), "task_reward_earned", "task", task_id)
            if row["thread_id"]:
                summary = deliverable if not external_ref else f"{deliverable}\n\nReference: {external_ref}"
                conn.execute(
                    """
                    INSERT INTO posts (thread_id, author_id, body, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (row["thread_id"], user["id"], summary, now),
                )
                conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, row["thread_id"]))
            updated = conn.execute(
                """
                SELECT
                    t.*,
                    creator.name AS creator_name,
                    assignee.name AS assignee_name
                FROM tasks t
                JOIN users creator ON creator.id = t.creator_id
                LEFT JOIN users assignee ON assignee.id = t.assignee_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
        return {
            "task": self._serialize_task(updated, int(user["id"])),
            "route_result": route_result,
        }

    def build_quote_for_user(self, token: str, payload: dict) -> dict:
        with self._connect() as conn:
            user = self._require_user(conn, token)
        order = self._task_order_from_payload(payload)
        quote = build_quote(order)
        return {
            "user": user,
            "order": asdict(quote.order),
            "candidates": [asdict(item) for item in quote.candidates],
        }

    def execute_for_user(self, token: str, payload: dict) -> dict:
        with self._connect() as conn:
            user = self._require_user(conn, token)
        order = self._task_order_from_payload(payload)
        result = execute(order, str(payload.get("provider", "")), str(payload.get("model", "")))
        return {
            "user": user,
            "result": asdict(result),
        }
