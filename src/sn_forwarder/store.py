from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    password_hash: str
    role: str
    balance: int
    is_active: int
    created_at: str


@dataclass(frozen=True)
class ProductRecord:
    id: int
    name: str
    button_label: str
    price: int
    is_active: int
    sort_order: int
    created_at: str


@dataclass(frozen=True)
class RequestRecord:
    id: int
    user_id: int
    product_id: int
    sn: str
    status: str
    reply_text: str | None
    error_text: str | None
    price_charged: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RequestWithProduct:
    id: int
    user_id: int
    product_id: int
    product_name: str
    sn: str
    status: str
    reply_text: str | None
    error_text: str | None
    price_charged: int
    created_at: str


@dataclass(frozen=True)
class ApiKeyRecord:
    id: int
    user_id: int
    api_key: str
    label: str | None
    is_active: int
    created_at: str


def _make_connection(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_all_tables(database_path: str) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _make_connection(database_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            balance INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            button_label TEXT NOT NULL,
            price INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            sn TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reply_text TEXT,
            error_text TEXT,
            price_charged INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            ref_request_id INTEGER REFERENCES requests(id),
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            api_key TEXT NOT NULL UNIQUE,
            label TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.close()


class UserStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        _init_all_tables(database_path)

    def create_user(self, username: str, password_hash: str, role: str = "user") -> int:
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN")
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, role),
            )
            uid = int(cursor.lastrowid)
            conn.execute("COMMIT")
            return uid
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def get_by_username(self, username: str) -> UserRecord | None:
        conn = _make_connection(self.database_path)
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        return UserRecord(**dict(row)) if row else None

    def get_by_id(self, user_id: int) -> UserRecord | None:
        conn = _make_connection(self.database_path)
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        return UserRecord(**dict(row)) if row else None

    def list_all(self) -> list[UserRecord]:
        conn = _make_connection(self.database_path)
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        conn.close()
        return [UserRecord(**dict(r)) for r in rows]

    def set_active(self, user_id: int, is_active: int) -> None:
        conn = _make_connection(self.database_path)
        conn.execute("BEGIN")
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
        conn.execute("COMMIT")
        conn.close()

    def _add_balance(self, user_id: int, amount: int) -> None:
        """Test/admin helper — use BalanceService.topup in production code."""
        conn = _make_connection(self.database_path)
        conn.execute("BEGIN")
        conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
        conn.execute("COMMIT")
        conn.close()


class ProductStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        _init_all_tables(database_path)

    def create_product(self, name: str, button_label: str, price: int, sort_order: int = 0) -> int:
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN")
            cursor = conn.execute(
                "INSERT INTO products (name, button_label, price, sort_order) VALUES (?,?,?,?)",
                (name, button_label, price, sort_order),
            )
            pid = int(cursor.lastrowid)
            conn.execute("COMMIT")
            return pid
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def list_active(self) -> list[ProductRecord]:
        conn = _make_connection(self.database_path)
        rows = conn.execute(
            "SELECT * FROM products WHERE is_active=1 ORDER BY sort_order, id"
        ).fetchall()
        conn.close()
        return [ProductRecord(**dict(r)) for r in rows]

    def list_all(self) -> list[ProductRecord]:
        conn = _make_connection(self.database_path)
        rows = conn.execute("SELECT * FROM products ORDER BY sort_order, id").fetchall()
        conn.close()
        return [ProductRecord(**dict(r)) for r in rows]

    def get_by_id(self, product_id: int) -> ProductRecord | None:
        conn = _make_connection(self.database_path)
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        conn.close()
        return ProductRecord(**dict(row)) if row else None

    def update(self, product_id: int, name: str, button_label: str, price: int, is_active: int, sort_order: int) -> None:
        conn = _make_connection(self.database_path)
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE products SET name=?,button_label=?,price=?,is_active=?,sort_order=? WHERE id=?",
            (name, button_label, price, is_active, sort_order, product_id),
        )
        conn.execute("COMMIT")
        conn.close()


class RequestStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        _init_all_tables(database_path)

    def create_order(self, user_id: int, product_id: int, sn: str, price: int) -> int | None:
        """Atomically debit balance + insert request + insert transaction. Returns request_id or None."""
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE users SET balance=balance-? WHERE id=? AND is_active=1 AND balance>=?",
                (price, user_id, price),
            )
            if cursor.rowcount == 0:
                conn.execute("ROLLBACK")
                return None
            new_balance = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()[0]
            req_cursor = conn.execute(
                "INSERT INTO requests (user_id, product_id, sn, status, price_charged) VALUES (?,?,?,'pending',?)",
                (user_id, product_id, sn, price),
            )
            request_id = int(req_cursor.lastrowid)
            conn.execute(
                "INSERT INTO transactions (user_id, type, amount, balance_after, ref_request_id) VALUES (?,'debit',?,?,?)",
                (user_id, price, new_balance, request_id),
            )
            conn.execute("COMMIT")
            return request_id
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def mark_sent(self, request_id: int) -> None:
        self._update_status(request_id, "processing", None, None)

    def mark_success(self, request_id: int, reply_text: str) -> None:
        self._update_status(request_id, "success", reply_text, None)

    def mark_failed(self, request_id: int, error_text: str) -> None:
        self._update_status(request_id, "failed", None, error_text)

    def get_request(self, request_id: int) -> RequestRecord:
        conn = _make_connection(self.database_path)
        row = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        conn.close()
        if row is None:
            raise KeyError(f"Request {request_id} not found")
        return RequestRecord(**dict(row))

    def get_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[RequestWithProduct]:
        conn = _make_connection(self.database_path)
        rows = conn.execute(
            """SELECT r.id, r.user_id, r.product_id, p.name AS product_name,
                      r.sn, r.status, r.reply_text, r.error_text, r.price_charged, r.created_at
               FROM requests r JOIN products p ON r.product_id=p.id
               WHERE r.user_id=? ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        ).fetchall()
        conn.close()
        return [RequestWithProduct(**dict(r)) for r in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> list[RequestWithProduct]:
        conn = _make_connection(self.database_path)
        rows = conn.execute(
            """SELECT r.id, r.user_id, r.product_id, p.name AS product_name,
                      r.sn, r.status, r.reply_text, r.error_text, r.price_charged, r.created_at
               FROM requests r JOIN products p ON r.product_id=p.id
               ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        conn.close()
        return [RequestWithProduct(**dict(r)) for r in rows]

    def _update_status(self, request_id: int, status: str, reply_text: str | None, error_text: str | None) -> None:
        conn = _make_connection(self.database_path)
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE requests SET status=?,reply_text=?,error_text=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, reply_text, error_text, request_id),
        )
        conn.execute("COMMIT")
        conn.close()


class ApiKeyStore:
    def __init__(self, database_path: str) -> None:
        _init_all_tables(database_path)
        self._db = database_path

    def create(self, user_id: int, label: str = "") -> str:
        api_key = secrets.token_hex(24)
        conn = _make_connection(self._db)
        conn.execute(
            "INSERT INTO api_keys (user_id, api_key, label) VALUES (?, ?, ?)",
            (user_id, api_key, label),
        )
        conn.commit()
        return api_key

    def get_by_key(self, api_key: str) -> ApiKeyRecord | None:
        conn = _make_connection(self._db)
        row = conn.execute(
            "SELECT * FROM api_keys WHERE api_key=? AND is_active=1", (api_key,)
        ).fetchone()
        return ApiKeyRecord(**dict(row)) if row else None

    def list_by_user(self, user_id: int) -> list[ApiKeyRecord]:
        conn = _make_connection(self._db)
        rows = conn.execute(
            "SELECT * FROM api_keys WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [ApiKeyRecord(**dict(r)) for r in rows]

    def list_all(self) -> list[ApiKeyRecord]:
        conn = _make_connection(self._db)
        rows = conn.execute(
            "SELECT * FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        return [ApiKeyRecord(**dict(r)) for r in rows]

    def revoke(self, key_id: int) -> None:
        conn = _make_connection(self._db)
        conn.execute("UPDATE api_keys SET is_active=0 WHERE id=?", (key_id,))
        conn.commit()
