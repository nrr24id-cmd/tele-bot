from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RequestRecord:
    id: int
    user_id: int
    chat_id: int
    sn: str
    command: str
    status: str
    reply_text: str | None
    error_text: str | None


class RequestStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        parent = Path(database_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def create_request(self, user_id: int, chat_id: int, sn: str, command: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO requests (user_id, chat_id, sn, command, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (user_id, chat_id, sn, command),
            )
            return int(cursor.lastrowid)

    def mark_sent(self, request_id: int) -> None:
        self._update(request_id, "sent", reply_text=None, error_text=None)

    def mark_success(self, request_id: int, reply_text: str) -> None:
        self._update(request_id, "success", reply_text=reply_text, error_text=None)

    def mark_failed(self, request_id: int, error_text: str) -> None:
        self._update(request_id, "failed", reply_text=None, error_text=error_text)

    def get_request(self, request_id: int) -> RequestRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, chat_id, sn, command, status, reply_text, error_text
                FROM requests
                WHERE id = ?
                """,
                (request_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Request {request_id} was not found")
        return RequestRecord(**dict(row))

    def _update(self, request_id: int, status: str, reply_text: str | None, error_text: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE requests
                SET status = ?, reply_text = ?, error_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, reply_text, error_text, request_id),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    sn TEXT NOT NULL,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reply_text TEXT,
                    error_text TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

