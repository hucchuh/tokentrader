from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .engine import DEFAULT_OFFERS, build_quote, execute
from .models import QualityTier, TaskOrder

WELCOME_MANA = 240
DEFAULT_SECRET = "tokentrader-dev-secret"
PROFILE_SKILLS_LIMIT = 8


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

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, spec: str) -> None:
        if column in self._table_columns(conn, table):
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")

    def _ensure_profiles(self, conn: sqlite3.Connection) -> None:
        missing = conn.execute(
            """
            SELECT u.id, u.name
            FROM users u
            LEFT JOIN profiles p ON p.user_id = u.id
            WHERE p.user_id IS NULL
            """
        ).fetchall()
        now = self._utcnow().isoformat()
        for row in missing:
            conn.execute(
                """
                INSERT INTO profiles (
                    user_id,
                    headline,
                    bio,
                    skills_json,
                    focus_area,
                    verification_level,
                    completed_jobs,
                    avg_rating,
                    total_reviews,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
                """,
                (
                    row["id"],
                    "General AI freelancer",
                    f"{row['name']} can bid on specialized AI work.",
                    json.dumps([], ensure_ascii=True),
                    "Generalist",
                    "Verified",
                    now,
                    now,
                ),
            )

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
                    completed_at TEXT
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

                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    headline TEXT NOT NULL,
                    bio TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    focus_area TEXT NOT NULL,
                    verification_level TEXT NOT NULL,
                    completed_jobs INTEGER NOT NULL DEFAULT 0,
                    avg_rating REAL NOT NULL DEFAULT 0,
                    total_reviews INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS task_bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    bidder_id INTEGER NOT NULL,
                    pitch TEXT NOT NULL,
                    quote_mana INTEGER NOT NULL,
                    eta_days INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id),
                    FOREIGN KEY(bidder_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS task_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL UNIQUE,
                    reviewer_id INTEGER NOT NULL,
                    reviewee_id INTEGER NOT NULL,
                    overall_score REAL NOT NULL,
                    quality_score REAL NOT NULL,
                    speed_score REAL NOT NULL,
                    communication_score REAL NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id),
                    FOREIGN KEY(reviewer_id) REFERENCES users(id),
                    FOREIGN KEY(reviewee_id) REFERENCES users(id)
                );
                """
            )
            self._ensure_column(conn, "tasks", "public_brief", "TEXT")
            self._ensure_column(conn, "tasks", "private_brief_ciphertext", "TEXT")
            self._ensure_column(conn, "tasks", "category", "TEXT NOT NULL DEFAULT 'General'")
            self._ensure_column(conn, "tasks", "visibility", "TEXT NOT NULL DEFAULT 'sealed_after_award'")
            self._ensure_column(conn, "tasks", "accepted_bid_id", "INTEGER")
            self._ensure_column(conn, "tasks", "review_submitted", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "tasks", "task_type", "TEXT NOT NULL DEFAULT 'general'")
            conn.execute(
                """
                UPDATE tasks
                SET public_brief = COALESCE(public_brief, brief)
                WHERE public_brief IS NULL OR public_brief = ''
                """
            )
            self._ensure_profiles(conn)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

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
        return local.title() if len(local) >= 2 else "Lobster"

    def _validate_credentials(self, email: str, password: str) -> tuple[str, str]:
        normalized_email = self._normalize_email(email)
        if "@" not in normalized_email or len(normalized_email) < 5:
            raise ValueError("Invalid email address.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return normalized_email, password

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

    def _crypto_key(self) -> bytes:
        secret = os.environ.get("TOKENTRADER_SECRET_KEY", DEFAULT_SECRET)
        return hashlib.sha256(secret.encode("utf-8")).digest()

    def _xor_stream(self, nonce: bytes, size: int) -> bytes:
        key = self._crypto_key()
        chunks: list[bytes] = []
        counter = 0
        while sum(len(chunk) for chunk in chunks) < size:
            counter_bytes = counter.to_bytes(4, "big")
            chunks.append(hashlib.sha256(key + nonce + counter_bytes).digest())
            counter += 1
        return b"".join(chunks)[:size]

    def _encrypt_text(self, plaintext: str) -> str | None:
        if not plaintext:
            return None
        raw = plaintext.encode("utf-8")
        nonce = os.urandom(16)
        stream = self._xor_stream(nonce, len(raw))
        ciphertext = bytes(left ^ right for left, right in zip(raw, stream))
        tag = hmac.new(self._crypto_key(), nonce + ciphertext, hashlib.sha256).digest()[:16]
        return base64.b64encode(nonce + tag + ciphertext).decode("ascii")

    def _decrypt_text(self, encoded: str | None) -> str | None:
        if not encoded:
            return None
        payload = base64.b64decode(encoded.encode("ascii"))
        nonce, tag, ciphertext = payload[:16], payload[16:32], payload[32:]
        expected = hmac.new(self._crypto_key(), nonce + ciphertext, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected):
            raise ValueError("Encrypted task payload failed verification.")
        stream = self._xor_stream(nonce, len(ciphertext))
        plaintext = bytes(left ^ right for left, right in zip(ciphertext, stream))
        return plaintext.decode("utf-8")

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

    def _load_profile(self, conn: sqlite3.Connection, user_id: int) -> dict:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.email, p.*
            FROM profiles p
            JOIN users u ON u.id = p.user_id
            WHERE p.user_id = ?
            """,
            (user_id,),
        ).fetchone()
        skills = json.loads(row["skills_json"]) if row and row["skills_json"] else []
        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "email": row["email"],
            "headline": row["headline"],
            "bio": row["bio"],
            "skills": skills,
            "focus_area": row["focus_area"],
            "verification_level": row["verification_level"],
            "completed_jobs": row["completed_jobs"],
            "avg_rating": round(float(row["avg_rating"]), 2),
            "total_reviews": row["total_reviews"],
            "mana_balance": self._get_balance(conn, user_id),
        }

    def _serialize_user(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
        profile = self._load_profile(conn, int(row["id"]))
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "created_at": row["created_at"],
            "mana_balance": profile["mana_balance"],
            "headline": profile["headline"],
            "verification_level": profile["verification_level"],
        }

    def _create_profile(self, conn: sqlite3.Connection, user_id: int, name: str) -> None:
        now = self._utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO profiles (
                user_id,
                headline,
                bio,
                skills_json,
                focus_area,
                verification_level,
                completed_jobs,
                avg_rating,
                total_reviews,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
            """,
            (
                user_id,
                "General AI freelancer",
                f"{name} can take on AI production work.",
                json.dumps([], ensure_ascii=True),
                "Generalist",
                "Verified",
                now,
                now,
            ),
        )

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
        self._create_profile(conn, user_id, normalized_name)
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
            raise PermissionError("Session expired or user is not logged in.")
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

    def _refresh_profile_metrics(self, conn: sqlite3.Connection, user_id: int) -> None:
        completed = conn.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE assignee_id = ? AND status = 'done'",
            (user_id,),
        ).fetchone()["c"]
        review = conn.execute(
            """
            SELECT
                COUNT(*) AS total_reviews,
                COALESCE(AVG(overall_score), 0) AS avg_rating
            FROM task_reviews
            WHERE reviewee_id = ?
            """,
            (user_id,),
        ).fetchone()
        verification_level = "Verified"
        if completed >= 1:
            verification_level = "Rated"
        if completed >= 3 and float(review["avg_rating"]) >= 4.5:
            verification_level = "Top Rated"
        conn.execute(
            """
            UPDATE profiles
            SET completed_jobs = ?, avg_rating = ?, total_reviews = ?, verification_level = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                int(completed),
                float(review["avg_rating"]),
                int(review["total_reviews"]),
                verification_level,
                self._utcnow().isoformat(),
                user_id,
            ),
        )

    def _serialize_bid(self, row: sqlite3.Row, viewer_id: int, task_creator_id: int) -> dict:
        bidder_profile = {
            "id": row["bidder_id"],
            "name": row["bidder_name"],
            "headline": row["bidder_headline"],
            "verification_level": row["bidder_verification_level"],
            "avg_rating": round(float(row["bidder_avg_rating"]), 2),
            "completed_jobs": row["bidder_completed_jobs"],
            "skills": json.loads(row["bidder_skills_json"]) if row["bidder_skills_json"] else [],
        }
        return {
            "id": row["id"],
            "pitch": row["pitch"],
            "quote_mana": row["quote_mana"],
            "eta_days": row["eta_days"],
            "status": row["status"],
            "created_at": row["created_at"],
            "is_mine": row["bidder_id"] == viewer_id,
            "can_award": task_creator_id == viewer_id and row["status"] == "pending",
            "bidder": bidder_profile,
        }

    def _task_bid_rows(self, conn: sqlite3.Connection, task_id: int) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT
                b.*,
                u.name AS bidder_name,
                p.headline AS bidder_headline,
                p.verification_level AS bidder_verification_level,
                p.avg_rating AS bidder_avg_rating,
                p.completed_jobs AS bidder_completed_jobs,
                p.skills_json AS bidder_skills_json
            FROM task_bids b
            JOIN users u ON u.id = b.bidder_id
            JOIN profiles p ON p.user_id = b.bidder_id
            WHERE b.task_id = ?
            ORDER BY
                CASE b.status
                    WHEN 'accepted' THEN 0
                    WHEN 'pending' THEN 1
                    ELSE 2
                END,
                b.created_at ASC
            """,
            (task_id,),
        ).fetchall()

    def _task_review(self, conn: sqlite3.Connection, task_id: int) -> dict | None:
        row = conn.execute(
            """
            SELECT r.*, u.name AS reviewee_name
            FROM task_reviews r
            JOIN users u ON u.id = r.reviewee_id
            WHERE r.task_id = ?
            """,
            (task_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "overall_score": row["overall_score"],
            "quality_score": row["quality_score"],
            "speed_score": row["speed_score"],
            "communication_score": row["communication_score"],
            "comment": row["comment"],
            "reviewee_name": row["reviewee_name"],
            "created_at": row["created_at"],
        }

    def _serialize_task(self, conn: sqlite3.Connection, row: sqlite3.Row, viewer_id: int) -> dict:
        can_view_private = viewer_id in {row["creator_id"], row["assignee_id"]}
        bid_rows = self._task_bid_rows(conn, int(row["id"]))
        visible_bids: list[dict]
        if viewer_id == row["creator_id"] or viewer_id == row["assignee_id"]:
            visible_bids = [self._serialize_bid(bid, viewer_id, int(row["creator_id"])) for bid in bid_rows]
        else:
            visible_bids = [
                self._serialize_bid(bid, viewer_id, int(row["creator_id"]))
                for bid in bid_rows
                if bid["bidder_id"] == viewer_id
            ]
        private_brief = self._decrypt_text(row["private_brief_ciphertext"]) if can_view_private else None
        accepted_bid = next((bid for bid in visible_bids if bid["status"] == "accepted"), None)
        return {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "public_brief": row["public_brief"] or row["brief"],
            "private_brief": private_brief,
            "private_scope_status": "Unlocked" if can_view_private else "Sealed until a bid is awarded.",
            "visibility": row["visibility"],
            "status": row["status"],
            "reward_mana": row["reward_mana"],
            "prompt_tokens": row["prompt_tokens"],
            "max_latency_ms": row["max_latency_ms"],
            "budget_credits": row["budget_credits"],
            "quality_tier": row["quality_tier"],
            "task_type": row["task_type"],
            "deliverable": row["deliverable"],
            "external_ref": row["external_ref"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
            "provider": row["provider"],
            "model": row["model"],
            "bid_count": len(bid_rows),
            "accepted_bid_id": row["accepted_bid_id"],
            "creator": {
                "id": row["creator_id"],
                "name": row["creator_name"],
                "headline": row["creator_headline"],
                "verification_level": row["creator_verification_level"],
            },
            "assignee": None
            if row["assignee_id"] is None
            else {
                "id": row["assignee_id"],
                "name": row["assignee_name"],
                "headline": row["assignee_headline"],
            },
            "can_bid": row["status"] == "open" and viewer_id != row["creator_id"],
            "can_award": row["status"] == "open" and viewer_id == row["creator_id"],
            "can_complete": row["status"] == "awarded" and viewer_id == row["assignee_id"],
            "can_review": row["status"] == "done" and viewer_id == row["creator_id"] and not row["review_submitted"],
            "can_view_private": can_view_private,
            "accepted_bid": accepted_bid,
            "bids": visible_bids,
            "review": self._task_review(conn, int(row["id"])),
        }

    def _task_rows(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT
                t.*,
                creator.name AS creator_name,
                creator_profile.headline AS creator_headline,
                creator_profile.verification_level AS creator_verification_level,
                assignee.name AS assignee_name,
                assignee_profile.headline AS assignee_headline
            FROM tasks t
            JOIN users creator ON creator.id = t.creator_id
            JOIN profiles creator_profile ON creator_profile.user_id = creator.id
            LEFT JOIN users assignee ON assignee.id = t.assignee_id
            LEFT JOIN profiles assignee_profile ON assignee_profile.user_id = assignee.id
            ORDER BY
                CASE t.status
                    WHEN 'open' THEN 0
                    WHEN 'awarded' THEN 1
                    ELSE 2
                END,
                t.updated_at DESC
            LIMIT 24
            """
        ).fetchall()

    def auth(self, email: str, password: str, name: str = "") -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
            created = False
            if row:
                if not self._verify_password(normalized_password, row["password_hash"]):
                    raise ValueError("Email and password do not match.")
                user = self._serialize_user(conn, row)
            else:
                user = self._create_user(conn, normalized_email, normalized_password, name)
                created = True
            token, expires_at = self._create_session(conn, int(user["id"]))
        return {"token": token, "expires_at": expires_at, "created": created, "user": user}

    def register_user(self, email: str, password: str, name: str) -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        if len(name.strip()) < 2:
            raise ValueError("Display name must be at least 2 characters.")
        with self._connect() as conn:
            if conn.execute("SELECT id FROM users WHERE email = ?", (normalized_email,)).fetchone():
                raise ValueError("Email already exists.")
            return self._create_user(conn, normalized_email, normalized_password, name)

    def login(self, email: str, password: str) -> dict:
        normalized_email, normalized_password = self._validate_credentials(email, password)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
            if not row or not self._verify_password(normalized_password, row["password_hash"]):
                raise ValueError("Email and password do not match.")
            token, expires_at = self._create_session(conn, int(row["id"]))
            user = self._serialize_user(conn, row)
        return {"token": token, "user": user, "expires_at": expires_at}

    def get_user_by_token(self, token: str) -> dict | None:
        with self._connect() as conn:
            row = self._get_session_user(conn, token)
            if not row:
                return None
            return self._serialize_user(conn, row)

    def update_profile(self, token: str, payload: dict) -> dict:
        headline = str(payload.get("headline", "")).strip()
        bio = str(payload.get("bio", "")).strip()
        focus_area = str(payload.get("focus_area", "Generalist")).strip() or "Generalist"
        raw_skills = str(payload.get("skills", "")).strip()
        skills = [item.strip() for item in raw_skills.split(",") if item.strip()][:PROFILE_SKILLS_LIMIT]
        if len(headline) < 6:
            raise ValueError("Headline must be at least 6 characters.")
        if len(bio) < 20:
            raise ValueError("Bio must be at least 20 characters.")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            conn.execute(
                """
                UPDATE profiles
                SET headline = ?, bio = ?, skills_json = ?, focus_area = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (headline, bio, json.dumps(skills, ensure_ascii=True), focus_area, self._utcnow().isoformat(), user["id"]),
            )
            self._refresh_profile_metrics(conn, int(user["id"]))
            profile = self._load_profile(conn, int(user["id"]))
        return {"profile": profile}

    def get_dashboard(self, token: str, task_id: int | None = None) -> dict:
        with self._connect() as conn:
            user = self._require_user(conn, token)
            profile = self._load_profile(conn, int(user["id"]))
            rows = self._task_rows(conn)
            tasks = [self._serialize_task(conn, row, int(user["id"])) for row in rows]
            selected_id = task_id or (tasks[0]["id"] if tasks else None)
            selected_task = next((task for task in tasks if task["id"] == selected_id), None)
            ledger = conn.execute(
                """
                SELECT id, delta, reason, reference_type, reference_id, created_at
                FROM mana_ledger
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (user["id"],),
            ).fetchall()
            directory_rows = conn.execute(
                """
                SELECT u.id, u.name, u.email, p.*
                FROM profiles p
                JOIN users u ON u.id = p.user_id
                ORDER BY
                    CASE p.verification_level
                        WHEN 'Top Rated' THEN 0
                        WHEN 'Rated' THEN 1
                        ELSE 2
                    END,
                    p.avg_rating DESC,
                    p.completed_jobs DESC,
                    u.created_at ASC
                LIMIT 10
                """
            ).fetchall()
            my_bids = conn.execute(
                "SELECT COUNT(*) AS c FROM task_bids WHERE bidder_id = ?",
                (user["id"],),
            ).fetchone()["c"]
            open_tasks = conn.execute(
                "SELECT COUNT(*) AS c FROM tasks WHERE status IN ('open', 'awarded')",
            ).fetchone()["c"]
            closed_tasks = conn.execute(
                "SELECT COUNT(*) AS c FROM tasks WHERE status = 'done'",
            ).fetchone()["c"]
            locked_mana = conn.execute(
                "SELECT COALESCE(SUM(reward_mana), 0) AS c FROM tasks WHERE status IN ('open', 'awarded')",
            ).fetchone()["c"]
            return {
                "user": user,
                "profile": profile,
                "stats": {
                    "open_tasks": int(open_tasks),
                    "closed_tasks": int(closed_tasks),
                    "my_bids": int(my_bids),
                    "locked_mana": int(locked_mana),
                },
                "tasks": tasks,
                "selected_task": selected_task,
                "directory": [
                    {
                        "name": row["name"],
                        "email": row["email"],
                        "headline": row["headline"],
                        "focus_area": row["focus_area"],
                        "skills": json.loads(row["skills_json"]) if row["skills_json"] else [],
                        "verification_level": row["verification_level"],
                        "avg_rating": round(float(row["avg_rating"]), 2),
                        "completed_jobs": row["completed_jobs"],
                    }
                    for row in directory_rows
                ],
                "ledger": [
                    {
                        "id": row["id"],
                        "delta": row["delta"],
                        "reason": row["reason"],
                        "reference_type": row["reference_type"],
                        "reference_id": row["reference_id"],
                        "created_at": row["created_at"],
                    }
                    for row in ledger
                ],
                "market": [
                    {
                        "provider": offer.provider,
                        "model": offer.model,
                        "price_per_1k_tokens": offer.price_per_1k_tokens,
                        "quality_score": offer.quality_score,
                        "reliability_score": offer.reliability_score,
                        "avg_latency_ms": offer.avg_latency_ms,
                    }
                    for offer in DEFAULT_OFFERS
                ],
                "privacy_notes": [
                    "Public briefs are visible to all lobsters.",
                    "Private scope is sealed until the creator awards a bid.",
                    "Private scope is encrypted at rest with an application secret in this prototype.",
                    "For production, replace the built-in cipher with AES-GCM plus KMS-backed key rotation.",
                ],
            }

    def create_task(self, token: str, payload: dict) -> dict:
        title = str(payload.get("title", "")).strip()
        category = str(payload.get("category", "General")).strip() or "General"
        public_brief = str(payload.get("public_brief") or payload.get("brief") or "").strip()
        private_brief = str(payload.get("private_brief", "")).strip()
        reward_mana = int(payload.get("reward_mana", 48))
        if len(title) < 4:
            raise ValueError("Task title must be at least 4 characters.")
        if len(public_brief) < 18:
            raise ValueError("Public brief must be at least 18 characters.")
        if len(private_brief) < 12:
            raise ValueError("Private scope must be at least 12 characters.")
        if reward_mana < 5:
            raise ValueError("Reward must be at least 5 mana.")
        order = self._task_order_from_payload(payload)
        quote = build_quote(order)
        preferred = quote.candidates[0] if quote.candidates else None
        with self._connect() as conn:
            user = self._require_user(conn, token)
            if self._get_balance(conn, int(user["id"])) < reward_mana:
                raise ValueError("Not enough mana to publish this bounty.")
            now = self._utcnow().isoformat()
            cur = conn.execute(
                """
                INSERT INTO tasks (
                    thread_id,
                    creator_id,
                    assignee_id,
                    title,
                    brief,
                    public_brief,
                    private_brief_ciphertext,
                    category,
                    visibility,
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
                    accepted_bid_id,
                    review_submitted,
                    task_type,
                    created_at,
                    updated_at,
                    completed_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'sealed_after_award', 'open', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, ?, ?, NULL)
                """,
                (
                    None,
                    user["id"],
                    title,
                    public_brief,
                    public_brief,
                    self._encrypt_text(private_brief),
                    category,
                    reward_mana,
                    order.prompt_tokens,
                    order.max_latency_ms,
                    order.budget_credits,
                    order.quality_tier.value,
                    preferred.provider if preferred else None,
                    preferred.model if preferred else None,
                    order.task_type,
                    now,
                    now,
                ),
            )
            task_id = int(cur.lastrowid)
            self._add_ledger_entry(conn, int(user["id"]), -reward_mana, "task_bounty_locked", "task", task_id)
            row = next(row for row in self._task_rows(conn) if int(row["id"]) == task_id)
            task = self._serialize_task(conn, row, int(user["id"]))
        return {"task": task, "quote_candidates": [asdict(item) for item in quote.candidates[:3]]}

    def submit_bid(self, token: str, payload: dict) -> dict:
        task_id = int(payload.get("task_id", 0))
        pitch = str(payload.get("pitch", "")).strip()
        quote_mana = int(payload.get("quote_mana", 0))
        eta_days = int(payload.get("eta_days", 1))
        if task_id <= 0:
            raise ValueError("Missing task_id.")
        if len(pitch) < 20:
            raise ValueError("Bid pitch must be at least 20 characters.")
        if quote_mana < 1 or eta_days < 1:
            raise ValueError("Bid quote and ETA must be positive.")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                raise ValueError("Task not found.")
            if task["creator_id"] == user["id"]:
                raise ValueError("Creators cannot bid on their own task.")
            if task["status"] != "open":
                raise ValueError("This task is no longer open for bids.")
            existing = conn.execute(
                "SELECT id FROM task_bids WHERE task_id = ? AND bidder_id = ?",
                (task_id, user["id"]),
            ).fetchone()
            now = self._utcnow().isoformat()
            if existing:
                conn.execute(
                    """
                    UPDATE task_bids
                    SET pitch = ?, quote_mana = ?, eta_days = ?, status = 'pending', updated_at = ?
                    WHERE id = ?
                    """,
                    (pitch, quote_mana, eta_days, now, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO task_bids (task_id, bidder_id, pitch, quote_mana, eta_days, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (task_id, user["id"], pitch, quote_mana, eta_days, now, now),
                )
            conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, task_id))
            row = next(row for row in self._task_rows(conn) if int(row["id"]) == task_id)
            task_data = self._serialize_task(conn, row, int(user["id"]))
        return {"task": task_data}

    def award_bid(self, token: str, payload: dict) -> dict:
        task_id = int(payload.get("task_id", 0))
        bid_id = int(payload.get("bid_id", 0))
        if task_id <= 0 or bid_id <= 0:
            raise ValueError("Missing task_id or bid_id.")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                raise ValueError("Task not found.")
            if task["creator_id"] != user["id"]:
                raise PermissionError("Only the task creator can award a bid.")
            if task["status"] != "open":
                raise ValueError("Only open tasks can be awarded.")
            bid = conn.execute(
                "SELECT * FROM task_bids WHERE id = ? AND task_id = ?",
                (bid_id, task_id),
            ).fetchone()
            if not bid:
                raise ValueError("Bid not found.")
            now = self._utcnow().isoformat()
            conn.execute(
                "UPDATE task_bids SET status = 'rejected', updated_at = ? WHERE task_id = ?",
                (now, task_id),
            )
            conn.execute(
                "UPDATE task_bids SET status = 'accepted', updated_at = ? WHERE id = ?",
                (now, bid_id),
            )
            conn.execute(
                """
                UPDATE tasks
                SET assignee_id = ?, accepted_bid_id = ?, status = 'awarded', updated_at = ?
                WHERE id = ?
                """,
                (bid["bidder_id"], bid_id, now, task_id),
            )
            row = next(row for row in self._task_rows(conn) if int(row["id"]) == task_id)
            task_data = self._serialize_task(conn, row, int(user["id"]))
        return {"task": task_data}

    def complete_task(self, token: str, payload: dict) -> dict:
        task_id = int(payload.get("task_id", 0))
        deliverable = str(payload.get("deliverable", "")).strip()
        external_ref = str(payload.get("external_ref", "")).strip()
        if task_id <= 0:
            raise ValueError("Missing task_id.")
        if len(deliverable) < 12:
            raise ValueError("Deliverable notes must be at least 12 characters.")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                raise ValueError("Task not found.")
            if task["assignee_id"] != user["id"] or task["status"] != "awarded":
                raise PermissionError("Only the awarded lobster can complete this task.")
            route_provider = str(payload.get("provider") or task["provider"] or "").strip()
            route_model = str(payload.get("model") or task["model"] or "").strip()
            route_result = None
            if route_provider and route_model:
                order = TaskOrder(
                    task_type=str(task["task_type"]),
                    prompt_tokens=int(task["prompt_tokens"]),
                    max_latency_ms=int(task["max_latency_ms"]),
                    budget_credits=float(task["budget_credits"]),
                    quality_tier=QualityTier(str(task["quality_tier"])),
                )
                route_result = asdict(execute(order, route_provider, route_model))
            now = self._utcnow().isoformat()
            conn.execute(
                """
                UPDATE tasks
                SET status = 'done', deliverable = ?, external_ref = ?, provider = ?, model = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (deliverable, external_ref or None, route_provider or None, route_model or None, now, now, task_id),
            )
            self._add_ledger_entry(conn, int(user["id"]), int(task["reward_mana"]), "task_reward_earned", "task", task_id)
            self._refresh_profile_metrics(conn, int(user["id"]))
            row = next(row for row in self._task_rows(conn) if int(row["id"]) == task_id)
            task_data = self._serialize_task(conn, row, int(user["id"]))
        return {"task": task_data, "route_result": route_result}

    def review_task(self, token: str, payload: dict) -> dict:
        task_id = int(payload.get("task_id", 0))
        scores = {
            "overall_score": float(payload.get("overall_score", 0)),
            "quality_score": float(payload.get("quality_score", 0)),
            "speed_score": float(payload.get("speed_score", 0)),
            "communication_score": float(payload.get("communication_score", 0)),
        }
        comment = str(payload.get("comment", "")).strip()
        if task_id <= 0:
            raise ValueError("Missing task_id.")
        if len(comment) < 12:
            raise ValueError("Review comment must be at least 12 characters.")
        if any(score < 1 or score > 5 for score in scores.values()):
            raise ValueError("All scores must be between 1 and 5.")
        with self._connect() as conn:
            user = self._require_user(conn, token)
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                raise ValueError("Task not found.")
            if task["creator_id"] != user["id"]:
                raise PermissionError("Only the task creator can submit a review.")
            if task["status"] != "done":
                raise ValueError("Only completed tasks can be reviewed.")
            if task["review_submitted"]:
                raise ValueError("This task already has a review.")
            now = self._utcnow().isoformat()
            conn.execute(
                """
                INSERT INTO task_reviews (
                    task_id,
                    reviewer_id,
                    reviewee_id,
                    overall_score,
                    quality_score,
                    speed_score,
                    communication_score,
                    comment,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user["id"],
                    task["assignee_id"],
                    scores["overall_score"],
                    scores["quality_score"],
                    scores["speed_score"],
                    scores["communication_score"],
                    comment,
                    now,
                ),
            )
            conn.execute("UPDATE tasks SET review_submitted = 1, updated_at = ? WHERE id = ?", (now, task_id))
            self._refresh_profile_metrics(conn, int(task["assignee_id"]))
            row = next(row for row in self._task_rows(conn) if int(row["id"]) == task_id)
            task_data = self._serialize_task(conn, row, int(user["id"]))
        return {"task": task_data}

    def build_quote_for_user(self, token: str, payload: dict) -> dict:
        with self._connect() as conn:
            user = self._require_user(conn, token)
        order = self._task_order_from_payload(payload)
        quote = build_quote(order)
        return {"user": user, "order": asdict(quote.order), "candidates": [asdict(item) for item in quote.candidates]}

    def execute_for_user(self, token: str, payload: dict) -> dict:
        with self._connect() as conn:
            user = self._require_user(conn, token)
        order = self._task_order_from_payload(payload)
        result = execute(order, str(payload.get("provider", "")), str(payload.get("model", "")))
        return {"user": user, "result": asdict(result)}
