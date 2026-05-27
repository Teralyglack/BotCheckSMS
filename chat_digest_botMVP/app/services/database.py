from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models import ExtractedMessage, OutputFormat


@dataclass(slots=True)
class HistoryRecord:
    request_id: int
    user_id: int
    output_format: str
    result_text: str
    message_count: int
    status: str
    error: str | None
    created_at: str


class DatabaseService:
    """SQLite storage for users, processed requests and history.

    SQLite is enough for an educational/production-practice MVP: it does not require a separate
    server, persists data between restarts and can later be replaced with PostgreSQL.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;

                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    output_format TEXT NOT NULL,
                    result_text TEXT NOT NULL,
                    message_count INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'success',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
                );

                CREATE TABLE IF NOT EXISTS request_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_requests_user_date
                    ON requests(telegram_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_request
                    ON request_messages(request_id);
                """
            )

    def upsert_user(self, telegram_id: int, username: str | None, full_name: str | None) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (telegram_id, username, full_name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    last_seen = excluded.last_seen
                """,
                (telegram_id, username, full_name, now, now),
            )

    def create_success_request(
        self,
        telegram_id: int,
        output_format: OutputFormat,
        result_text: str,
        messages: list[ExtractedMessage],
    ) -> int:
        created_at = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO requests (telegram_id, output_format, result_text, message_count, status, error, created_at)
                VALUES (?, ?, ?, ?, 'success', NULL, ?)
                """,
                (telegram_id, output_format.value, result_text, len(messages), created_at),
            )
            request_id = int(cursor.lastrowid)
            conn.executemany(
                """
                INSERT INTO request_messages (request_id, role, kind, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        request_id,
                        item.role,
                        item.kind.value,
                        item.content,
                        item.created_at.isoformat(),
                    )
                    for item in messages
                ],
            )
            return request_id

    def create_failed_request(
        self,
        telegram_id: int,
        output_format: str,
        error: str,
        messages: list[ExtractedMessage],
    ) -> int:
        created_at = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO requests (telegram_id, output_format, result_text, message_count, status, error, created_at)
                VALUES (?, ?, '', ?, 'failed', ?, ?)
                """,
                (telegram_id, output_format, len(messages), error[:1000], created_at),
            )
            return int(cursor.lastrowid)

    def list_user_history(self, telegram_id: int, limit: int = 10) -> list[HistoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, telegram_id, output_format, result_text, message_count, status, error, created_at
                FROM requests
                WHERE telegram_id = ? AND status = 'success'
                ORDER BY id DESC
                LIMIT ?
                """,
                (telegram_id, limit),
            ).fetchall()
        return [self._history_record(row) for row in rows]

    def get_request(self, request_id: int) -> tuple[HistoryRecord, list[dict[str, Any]]] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, telegram_id, output_format, result_text, message_count, status, error, created_at
                FROM requests
                WHERE id = ?
                """,
                (request_id,),
            ).fetchone()
            if not row:
                return None
            message_rows = conn.execute(
                """
                SELECT role, kind, content, created_at
                FROM request_messages
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            ).fetchall()
        messages = [dict(row) for row in message_rows]
        return self._history_record(row), messages

    def get_admin_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_requests = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
            successful_requests = conn.execute(
                "SELECT COUNT(*) FROM requests WHERE status = 'success'"
            ).fetchone()[0]
            failed_requests = conn.execute("SELECT COUNT(*) FROM requests WHERE status = 'failed'").fetchone()[0]
            total_messages = conn.execute("SELECT COUNT(*) FROM request_messages").fetchone()[0]
            format_rows = conn.execute(
                """
                SELECT output_format, COUNT(*) AS count
                FROM requests
                WHERE status = 'success'
                GROUP BY output_format
                ORDER BY count DESC
                """
            ).fetchall()
            kind_rows = conn.execute(
                """
                SELECT kind, COUNT(*) AS count
                FROM request_messages
                GROUP BY kind
                ORDER BY count DESC
                """
            ).fetchall()
            last_rows = conn.execute(
                """
                SELECT r.id, r.telegram_id, u.username, u.full_name, r.output_format, r.message_count, r.status, r.created_at
                FROM requests r
                LEFT JOIN users u ON u.telegram_id = r.telegram_id
                ORDER BY r.id DESC
                LIMIT 5
                """
            ).fetchall()
        return {
            "total_users": total_users,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "total_messages": total_messages,
            "formats": [dict(row) for row in format_rows],
            "kinds": [dict(row) for row in kind_rows],
            "last_requests": [dict(row) for row in last_rows],
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _history_record(row: sqlite3.Row) -> HistoryRecord:
        return HistoryRecord(
            request_id=int(row["id"]),
            user_id=int(row["telegram_id"]),
            output_format=str(row["output_format"]),
            result_text=str(row["result_text"]),
            message_count=int(row["message_count"]),
            status=str(row["status"]),
            error=str(row["error"]) if row["error"] is not None else None,
            created_at=str(row["created_at"]),
        )
