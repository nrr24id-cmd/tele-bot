# SN Forwarder Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-user web panel (FastAPI + Jinja2) on top of the existing Telethon core so users can submit SN registration requests, consume balance per request, and see history — all running as one process on a local PC.

**Architecture:** Single asyncio process: FastAPI (panel web) + RegistrationWorker (serial queue) + Telethon (akun owner) berjalan bersama via `asyncio.gather`. SQLite WAL mode untuk concurrency. Cloudflare Tunnel untuk HTTPS publik.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, Telethon, passlib[bcrypt], itsdangerous, python-multipart, pytest, pytest-asyncio.

## Global Constraints

- Satu proses asyncio — FastAPI, worker, Telethon harus `gather`-ed di `main.py`.
- `python-telegram-bot` dihapus — tidak ada bot Telegram ingress di MVP ini.
- Semua uang: integer rupiah, tidak ada float.
- Potong saldo atomik — satu `BEGIN IMMEDIATE` yang mencakup debit + insert request + insert transaksi.
- WAL mode SQLite — aktifkan di `_init_schema` pertama kali.
- Password hash dengan bcrypt via `passlib`.
- Sesi via `SessionMiddleware` (Starlette), secret dari env `SESSION_SECRET`.
- CSRF token disimpan di sesi, divalidasi di tiap POST.
- TelethonTargetClient: 3 langkah — `/placeorder` → klik tombol → kirim SN → get_response.
- `PYTHONPATH=src` untuk semua perintah pytest dan run.
- Hapus `data/requests.sqlite3` lama sebelum first run (schema berubah total).

---

## File Structure

```
src/sn_forwarder/
├── config.py              # DIREVISI: hapus bot fields, tambah WEB_* & SESSION_SECRET
├── store.py               # DIREVISI: UserStore, ProductStore, RequestStore (schema baru)
├── balance.py             # BARU: BalanceService (topup, refund, ledger)
├── target_client.py       # DIREVISI: 3-step Telethon flow
├── worker.py              # DIREVISI: RegistrationJob baru, refund on fail
├── main.py                # DIREVISI: uvicorn + worker + telethon, tanpa bot
├── setup_admin.py         # BARU: script buat akun admin pertama kali
└── web/
    ├── __init__.py
    ├── app.py             # FastAPI factory + middleware
    ├── auth.py            # session, login, CSRF, brute-force
    ├── routes_panel.py    # user routes + templates
    ├── routes_admin.py    # admin routes + templates
    ├── templates/
    │   ├── base.html
    │   ├── login.html
    │   ├── dashboard.html
    │   ├── order.html
    │   ├── history.html
    │   ├── transactions.html
    │   └── admin/
    │       ├── users.html
    │       ├── products.html
    │       └── history.html
    └── static/
        └── style.css

tests/
├── test_config.py         # DIREVISI
├── test_store.py          # DIREVISI
├── test_balance.py        # BARU
├── test_target_client.py  # BARU
├── test_worker.py         # DIREVISI
├── test_web_auth.py       # BARU
├── test_web_panel.py      # BARU
└── test_web_admin.py      # BARU
```

File dihapus: `src/sn_forwarder/bot_app.py`, `tests/test_bot_app.py`

---

### Task 1: Cleanup — Hapus Bot Ingress, Update Deps & Config

**Files:**
- Delete: `src/sn_forwarder/bot_app.py`
- Delete: `tests/test_bot_app.py`
- Modify: `requirements.txt`
- Modify: `src/sn_forwarder/config.py`
- Modify: `.env.example`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` dengan fields: `api_id: int`, `api_hash: str`, `target_bot_username: str`, `reply_timeout_seconds: float`, `database_path: str`, `telethon_session_name: str`, `session_secret: str`, `web_host: str`, `web_port: int`
- Produces: `load_settings(env) -> Settings`

- [ ] **Step 1: Hapus file bot lama**

```bash
rm src/sn_forwarder/bot_app.py
rm tests/test_bot_app.py
```

- [ ] **Step 2: Update `requirements.txt`**

```text
python-dotenv==1.0.1
Telethon==1.38.1
fastapi==0.115.5
uvicorn[standard]==0.32.1
jinja2==3.1.4
python-multipart==0.0.12
passlib[bcrypt]==1.7.4
itsdangerous==2.2.0
pytest==8.3.4
pytest-asyncio==0.25.2
httpx==0.28.1
```

- [ ] **Step 3: Install dependensi baru**

```powershell
.\.venv\Scripts\pip install -r requirements.txt
```

Expected: semua install tanpa error. `python-telegram-bot` tidak ada lagi.

- [ ] **Step 4: Tulis failing test config baru**

Ganti isi `tests/test_config.py`:

```python
import pytest
from sn_forwarder.config import ConfigError, load_settings


def valid_env():
    return {
        "API_ID": "12345",
        "API_HASH": "hash",
        "TARGET_BOT_USERNAME": "@target_bot",
        "REPLY_TIMEOUT_SECONDS": "60",
        "DATABASE_PATH": "data/requests.sqlite3",
        "TELETHON_SESSION_NAME": "owner_session",
        "SESSION_SECRET": "supersecret",
        "WEB_HOST": "127.0.0.1",
        "WEB_PORT": "8000",
    }


def test_load_settings_parses_values():
    s = load_settings(valid_env())
    assert s.api_id == 12345
    assert s.api_hash == "hash"
    assert s.target_bot_username == "@target_bot"
    assert s.session_secret == "supersecret"
    assert s.web_host == "127.0.0.1"
    assert s.web_port == 8000


def test_load_settings_rejects_missing_api_id():
    env = valid_env()
    env.pop("API_ID")
    with pytest.raises(ConfigError, match="API_ID"):
        load_settings(env)


def test_load_settings_rejects_missing_session_secret():
    env = valid_env()
    env.pop("SESSION_SECRET")
    with pytest.raises(ConfigError, match="SESSION_SECRET"):
        load_settings(env)


def test_load_settings_rejects_invalid_port():
    env = valid_env()
    env["WEB_PORT"] = "abc"
    with pytest.raises(ConfigError, match="WEB_PORT"):
        load_settings(env)
```

- [ ] **Step 5: Run test — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```

Expected: ImportError atau AssertionError karena `Settings` masih punya field lama.

- [ ] **Step 6: Tulis ulang `src/sn_forwarder/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    target_bot_username: str
    reply_timeout_seconds: float
    database_path: str
    telethon_session_name: str
    session_secret: str
    web_host: str
    web_port: int


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ

    return Settings(
        api_id=_parse_int(_required(env, "API_ID"), "API_ID"),
        api_hash=_required(env, "API_HASH"),
        target_bot_username=_required(env, "TARGET_BOT_USERNAME"),
        reply_timeout_seconds=_parse_float(
            env.get("REPLY_TIMEOUT_SECONDS", "60"), "REPLY_TIMEOUT_SECONDS"
        ),
        database_path=env.get("DATABASE_PATH", "data/requests.sqlite3").strip(),
        telethon_session_name=env.get("TELETHON_SESSION_NAME", "owner_session").strip(),
        session_secret=_required(env, "SESSION_SECRET"),
        web_host=env.get("WEB_HOST", "127.0.0.1").strip(),
        web_port=_parse_int(env.get("WEB_PORT", "8000"), "WEB_PORT"),
    )


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is required")
    return value


def _parse_int(value: str, key: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer") from exc


def _parse_float(value: str, key: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number") from exc
    if parsed <= 0:
        raise ConfigError(f"{key} must be greater than zero")
    return parsed
```

- [ ] **Step 7: Update `.env.example`**

```text
API_ID=123456
API_HASH=replace_me
TARGET_BOT_USERNAME=@target_bot_username
REPLY_TIMEOUT_SECONDS=60
DATABASE_PATH=data/requests.sqlite3
TELETHON_SESSION_NAME=owner_session
SESSION_SECRET=ganti_dengan_string_acak_minimal_32_karakter
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

- [ ] **Step 8: Run test — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add requirements.txt src/sn_forwarder/config.py .env.example tests/test_config.py
git rm src/sn_forwarder/bot_app.py tests/test_bot_app.py
git commit -m "feat: remove telegram bot ingress, add web config fields"
```

---

### Task 2: Schema — UserStore, ProductStore, RequestStore Revisi

**Files:**
- Modify: `src/sn_forwarder/store.py` (tulis ulang)
- Modify: `tests/test_store.py` (tulis ulang)

**Interfaces:**
- Produces: `UserRecord(id, username, password_hash, role, balance, is_active, created_at)`
- Produces: `ProductRecord(id, name, button_label, price, is_active, sort_order)`
- Produces: `RequestRecord(id, user_id, product_id, sn, status, reply_text, error_text, price_charged, created_at, updated_at)`
- Produces: `RequestWithProduct(id, user_id, product_id, product_name, sn, status, reply_text, error_text, price_charged, created_at)`
- Produces: `UserStore(database_path)`
- Produces: `ProductStore(database_path)`
- Produces: `RequestStore(database_path)` dengan method: `mark_sent`, `mark_success`, `mark_failed`, `get_request`, `get_by_user`, `get_all`, `create_order`

- [ ] **Step 1: Tulis failing tests**

Ganti isi `tests/test_store.py`:

```python
import pytest
from sn_forwarder.store import ProductStore, RequestStore, UserStore


def test_user_store_create_and_get(tmp_path):
    store = UserStore(str(tmp_path / "db.sqlite3"))
    uid = store.create_user("alice", "hash_abc", role="user")
    user = store.get_by_username("alice")
    assert user is not None
    assert user.id == uid
    assert user.role == "user"
    assert user.balance == 0
    assert user.is_active == 1


def test_user_store_duplicate_username_raises(tmp_path):
    store = UserStore(str(tmp_path / "db.sqlite3"))
    store.create_user("alice", "hash")
    with pytest.raises(Exception):
        store.create_user("alice", "hash2")


def test_user_store_set_active(tmp_path):
    store = UserStore(str(tmp_path / "db.sqlite3"))
    uid = store.create_user("alice", "hash")
    store.set_active(uid, 0)
    assert store.get_by_id(uid).is_active == 0


def test_product_store_create_and_list(tmp_path):
    store = ProductStore(str(tmp_path / "db.sqlite3"))
    pid = store.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    products = store.list_active()
    assert len(products) == 1
    assert products[0].id == pid
    assert products[0].button_label == "Amrr Activator Pro Tool A12+"


def test_product_store_inactive_excluded(tmp_path):
    store = ProductStore(str(tmp_path / "db.sqlite3"))
    pid = store.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    store.update(pid, "A12+", "Amrr Activator Pro Tool A12+", 50000, 0, 0)
    assert store.list_active() == []


def test_request_store_create_order_success(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 100000)
    pid = products.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)

    request_id = requests.create_order(uid, pid, "SN123", 50000)
    assert request_id is not None
    assert users.get_by_id(uid).balance == 50000
    record = requests.get_request(request_id)
    assert record.status == "pending"
    assert record.price_charged == 50000


def test_request_store_create_order_insufficient_balance(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    pid = products.create_product("A12+", "btn", 50000)

    result = requests.create_order(uid, pid, "SN123", 50000)
    assert result is None
    assert users.get_by_id(uid).balance == 0


def test_request_store_lifecycle(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 100000)
    pid = products.create_product("A12+", "btn", 50000)
    rid = requests.create_order(uid, pid, "SN123", 50000)

    requests.mark_success(rid, "Aktivasi berhasil")
    record = requests.get_request(rid)
    assert record.status == "success"
    assert record.reply_text == "Aktivasi berhasil"


def test_request_store_get_by_user(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 200000)
    pid = products.create_product("A12+", "btn", 50000)
    requests.create_order(uid, pid, "SN1", 50000)
    requests.create_order(uid, pid, "SN2", 50000)

    rows = requests.get_by_user(uid)
    assert len(rows) == 2
    assert rows[0].product_name == "A12+"
```

- [ ] **Step 2: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_store.py -v
```

Expected: ImportError karena `UserStore`, `ProductStore` belum ada.

- [ ] **Step 3: Tulis ulang `src/sn_forwarder/store.py`**

```python
from __future__ import annotations

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
```

- [ ] **Step 4: Run — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_store.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/store.py tests/test_store.py
git commit -m "feat: expand store with users, products, requests revision, transactions"
```

---

### Task 3: BalanceService

**Files:**
- Create: `src/sn_forwarder/balance.py`
- Create: `tests/test_balance.py`

**Interfaces:**
- Consumes: `_make_connection`, `_init_all_tables` dari `store.py`
- Produces: `TransactionRecord(id, user_id, type, amount, balance_after, ref_request_id, note, created_at)`
- Produces: `BalanceService(database_path)`
- Produces: `BalanceService.topup(user_id, amount, note) -> None`
- Produces: `BalanceService.refund(user_id, amount, ref_request_id) -> None`
- Produces: `BalanceService.get_transactions(user_id, limit) -> list[TransactionRecord]`

- [ ] **Step 1: Tulis failing test**

Buat `tests/test_balance.py`:

```python
import pytest
from sn_forwarder.balance import BalanceService
from sn_forwarder.store import UserStore


def test_topup_increases_balance(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")

    balance.topup(uid, 100000, "manual topup")

    assert users.get_by_id(uid).balance == 100000


def test_topup_records_transaction(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")
    balance.topup(uid, 50000, "test")

    txns = balance.get_transactions(uid)
    assert len(txns) == 1
    assert txns[0].type == "topup"
    assert txns[0].amount == 50000
    assert txns[0].balance_after == 50000
    assert txns[0].note == "test"


def test_refund_increases_balance(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 100000)

    balance.refund(uid, 50000, ref_request_id=1)

    assert users.get_by_id(uid).balance == 150000


def test_refund_records_transaction(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 100000)
    balance.refund(uid, 50000, ref_request_id=1)

    txns = balance.get_transactions(uid)
    assert txns[0].type == "refund"
    assert txns[0].ref_request_id == 1
```

- [ ] **Step 2: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_balance.py -v
```

Expected: ImportError karena `balance.py` belum ada.

- [ ] **Step 3: Buat `src/sn_forwarder/balance.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from .store import _init_all_tables, _make_connection


@dataclass(frozen=True)
class TransactionRecord:
    id: int
    user_id: int
    type: str
    amount: int
    balance_after: int
    ref_request_id: int | None
    note: str | None
    created_at: str


class BalanceService:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        _init_all_tables(database_path)

    def topup(self, user_id: int, amount: int, note: str = "") -> None:
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
            new_bal = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO transactions (user_id,type,amount,balance_after,note) VALUES (?,'topup',?,?,?)",
                (user_id, amount, new_bal, note or None),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def refund(self, user_id: int, amount: int, ref_request_id: int) -> None:
        conn = _make_connection(self.database_path)
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
            new_bal = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO transactions (user_id,type,amount,balance_after,ref_request_id) VALUES (?,'refund',?,?,?)",
                (user_id, amount, new_bal, ref_request_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def get_transactions(self, user_id: int, limit: int = 50) -> list[TransactionRecord]:
        conn = _make_connection(self.database_path)
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        conn.close()
        return [TransactionRecord(**dict(r)) for r in rows]
```

- [ ] **Step 4: Run — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_balance.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/balance.py tests/test_balance.py
git commit -m "feat: add balance service (topup, refund, ledger)"
```

---

### Task 4: TelethonTargetClient — 3-Step Flow

**Files:**
- Modify: `src/sn_forwarder/target_client.py`
- Create: `tests/test_target_client.py`

**Interfaces:**
- Produces: `TargetClientProtocol.send_and_wait(button_label: str, sn: str, timeout_seconds: float) -> str`
- Produces: `TelethonTargetClient(client, target_bot_username)`

- [ ] **Step 1: Tulis failing test**

Buat `tests/test_target_client.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sn_forwarder.target_client import TelethonTargetClient


def make_client(reply_text: str = "Sukses", click_raises: Exception | None = None):
    """Build a mock Telethon client whose conversation returns a reply."""
    mock_response = MagicMock()
    mock_response.raw_text = reply_text

    mock_button_msg = MagicMock()
    if click_raises:
        mock_button_msg.click = AsyncMock(side_effect=click_raises)
    else:
        mock_button_msg.click = AsyncMock()

    mock_conv = AsyncMock()
    mock_conv.send_message = AsyncMock()
    mock_conv.get_response = AsyncMock(side_effect=[mock_button_msg, mock_response])
    mock_conv.__aenter__ = AsyncMock(return_value=mock_conv)
    mock_conv.__aexit__ = AsyncMock(return_value=False)

    mock_telethon = AsyncMock()
    mock_telethon.get_entity = AsyncMock(return_value=MagicMock())
    mock_telethon.conversation = MagicMock(return_value=mock_conv)

    return mock_telethon


@pytest.mark.asyncio
async def test_sends_three_steps():
    client = make_client("Aktivasi berhasil")
    tc = TelethonTargetClient(client, "@bot")

    result = await tc.send_and_wait("Amrr Activator Pro Tool A12+", "SN123", 30.0)

    assert result == "Aktivasi berhasil"
    conv = client.conversation.return_value.__aenter__.return_value
    conv.send_message.assert_any_await("/placeorder")
    conv.send_message.assert_any_await("SN123")
    conv.get_response.return_value.click.assert_awaited_once_with(text="Amrr Activator Pro Tool A12+")


@pytest.mark.asyncio
async def test_timeout_raises():
    client = make_client()
    client.conversation.return_value.__aenter__.return_value.get_response = AsyncMock(
        side_effect=asyncio.TimeoutError
    )
    tc = TelethonTargetClient(client, "@bot")

    with pytest.raises(asyncio.TimeoutError):
        await tc.send_and_wait("btn", "SN", 0.01)
```

- [ ] **Step 2: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_target_client.py -v
```

Expected: FAIL karena signature `send_and_wait` lama hanya terima `command, timeout`.

- [ ] **Step 3: Tulis ulang `src/sn_forwarder/target_client.py`**

```python
from __future__ import annotations

from typing import Protocol

from telethon import TelegramClient


class TargetClientProtocol(Protocol):
    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        ...


class TelethonTargetClient:
    def __init__(self, client: TelegramClient, target_bot_username: str) -> None:
        self.client = client
        self.target_bot_username = target_bot_username

    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        target = await self.client.get_entity(self.target_bot_username)
        async with self.client.conversation(target, timeout=timeout_seconds) as conv:
            await conv.send_message("/placeorder")
            button_msg = await conv.get_response()
            await button_msg.click(text=button_label)
            await conv.send_message(sn)
            reply = await conv.get_response()
        return reply.raw_text or ""
```

- [ ] **Step 4: Run — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_target_client.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/target_client.py tests/test_target_client.py
git commit -m "feat: revise TelethonTargetClient to 3-step placeorder flow"
```

---

### Task 5: RegistrationWorker Revisi

**Files:**
- Modify: `src/sn_forwarder/worker.py`
- Modify: `tests/test_worker.py`

**Interfaces:**
- Consumes: `RequestStore.mark_sent/success/failed`, `BalanceService.refund`, `TargetClientProtocol.send_and_wait(button_label, sn, timeout)`
- Produces: `RegistrationJob(request_id, user_id, product_id, sn, button_label, price_charged)`
- Produces: `RegistrationWorker(store, balance, target_client)`
- Produces: `RegistrationWorker.enqueue(job) -> int`
- Produces: `RegistrationWorker.process_one(job) -> None`
- Produces: `RegistrationWorker.run_forever() -> None`

- [ ] **Step 1: Tulis failing test**

Ganti isi `tests/test_worker.py`:

```python
import asyncio
import pytest
from sn_forwarder.balance import BalanceService
from sn_forwarder.store import ProductStore, RequestStore, UserStore
from sn_forwarder.worker import RegistrationJob, RegistrationWorker


class FakeTargetClient:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        self.calls.append((button_label, sn))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def make_worker(tmp_path, reply: str | Exception = "OK"):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 200000)
    pid = products.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    store = RequestStore(db)
    balance = BalanceService(db)
    rid = store.create_order(uid, pid, "SN123", 50000)
    job = RegistrationJob(
        request_id=rid,
        user_id=uid,
        product_id=pid,
        sn="SN123",
        button_label="Amrr Activator Pro Tool A12+",
        price_charged=50000,
    )
    target = FakeTargetClient(reply)
    worker = RegistrationWorker(store, balance, target, reply_timeout_seconds=5.0)
    return worker, job, store, users, uid


@pytest.mark.asyncio
async def test_worker_success(tmp_path):
    worker, job, store, users, uid = make_worker(tmp_path, "Aktivasi berhasil")
    await worker.process_one(job)
    assert store.get_request(job.request_id).status == "success"
    assert store.get_request(job.request_id).reply_text == "Aktivasi berhasil"
    assert users.get_by_id(uid).balance == 150000  # saldo tidak dikembalikan


@pytest.mark.asyncio
async def test_worker_timeout_refunds(tmp_path):
    worker, job, store, users, uid = make_worker(tmp_path, asyncio.TimeoutError())
    await worker.process_one(job)
    assert store.get_request(job.request_id).status == "failed"
    assert users.get_by_id(uid).balance == 200000  # saldo dikembalikan


@pytest.mark.asyncio
async def test_worker_error_refunds(tmp_path):
    worker, job, store, users, uid = make_worker(tmp_path, RuntimeError("koneksi gagal"))
    await worker.process_one(job)
    assert store.get_request(job.request_id).status == "failed"
    assert users.get_by_id(uid).balance == 200000


@pytest.mark.asyncio
async def test_worker_enqueue_returns_qsize(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    store = RequestStore(db)
    balance = BalanceService(db)
    worker = RegistrationWorker(store, balance, FakeTargetClient("ok"), reply_timeout_seconds=5.0)
    job = RegistrationJob(1, 1, 1, "SN", "btn", 50000)
    size = await worker.enqueue(job)
    assert size == 1
```

- [ ] **Step 2: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_worker.py -v
```

- [ ] **Step 3: Tulis ulang `src/sn_forwarder/worker.py`**

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from .balance import BalanceService
from .store import RequestStore

logger = logging.getLogger(__name__)


class TargetClientProtocol(Protocol):
    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        ...


@dataclass(frozen=True)
class RegistrationJob:
    request_id: int
    user_id: int
    product_id: int
    sn: str
    button_label: str
    price_charged: int


class RegistrationWorker:
    def __init__(
        self,
        store: RequestStore,
        balance: BalanceService,
        target_client: TargetClientProtocol,
        reply_timeout_seconds: float,
    ) -> None:
        self.store = store
        self.balance = balance
        self.target_client = target_client
        self.reply_timeout_seconds = reply_timeout_seconds
        self.queue: asyncio.Queue[RegistrationJob] = asyncio.Queue()

    async def enqueue(self, job: RegistrationJob) -> int:
        await self.queue.put(job)
        return self.queue.qsize()

    async def run_forever(self) -> None:
        while True:
            job = await self.queue.get()
            try:
                await self.process_one(job)
            except Exception:
                logger.exception("Unexpected error processing job %s", job.request_id)
            finally:
                self.queue.task_done()

    async def process_one(self, job: RegistrationJob) -> None:
        self.store.mark_sent(job.request_id)
        try:
            reply = await self.target_client.send_and_wait(
                job.button_label, job.sn, self.reply_timeout_seconds
            )
        except asyncio.TimeoutError:
            self.store.mark_failed(job.request_id, "timeout")
            self.balance.refund(job.user_id, job.price_charged, job.request_id)
        except Exception as exc:
            logger.exception("Registration request %s failed", job.request_id)
            self.store.mark_failed(job.request_id, str(exc))
            self.balance.refund(job.user_id, job.price_charged, job.request_id)
        else:
            self.store.mark_success(job.request_id, reply or "Bot tujuan membalas tanpa teks.")
```

- [ ] **Step 4: Run — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_worker.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full test suite**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest -q
```

Expected: semua pass (config, store, balance, target_client, worker).

- [ ] **Step 6: Commit**

```bash
git add src/sn_forwarder/worker.py tests/test_worker.py
git commit -m "feat: revise worker for multi-product, refund on fail"
```

---

### Task 6: FastAPI App + Session Auth

**Files:**
- Create: `src/sn_forwarder/web/__init__.py`
- Create: `src/sn_forwarder/web/app.py`
- Create: `src/sn_forwarder/web/auth.py`
- Create: `tests/test_web_auth.py`

**Interfaces:**
- Consumes: `Settings`, `UserStore`, `ProductStore`, `RequestStore`, `BalanceService`
- Produces: `build_web_app(settings, user_store, product_store, request_store, balance_service) -> FastAPI`
- Produces: `hash_password(plain: str) -> str`
- Produces: `verify_password(plain: str, hashed: str) -> bool`
- Produces: `get_csrf_token(request) -> str`
- Produces: `verify_csrf(request, token: str) -> bool`
- Produces: FastAPI dependency `get_current_user(request) -> UserRecord` (raises 302 if not logged in)
- Produces: FastAPI dependency `get_current_admin(request) -> UserRecord` (raises 403 if not admin)

- [ ] **Step 1: Buat `src/sn_forwarder/web/__init__.py`**

```python
```

(kosong)

- [ ] **Step 2: Tulis failing test**

Buat `tests/test_web_auth.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sn_forwarder.balance import BalanceService
from sn_forwarder.config import Settings
from sn_forwarder.store import ProductStore, RequestStore, UserStore
from sn_forwarder.web.app import build_web_app
from sn_forwarder.web.auth import hash_password


def make_settings():
    return Settings(
        api_id=1, api_hash="h", target_bot_username="@b",
        reply_timeout_seconds=30.0, database_path=":memory:",
        telethon_session_name="s", session_secret="testsecret1234567890",
        web_host="127.0.0.1", web_port=8000,
    )


def make_app(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    settings = make_settings()
    user_store = UserStore(db)
    product_store = ProductStore(db)
    request_store = RequestStore(db)
    balance_service = BalanceService(db)
    user_store.create_user("admin", hash_password("adminpass"), role="admin")
    user_store.create_user("user1", hash_password("userpass"), role="user")
    app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker=None)
    return app


@pytest.mark.asyncio
async def test_login_success(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/login", data={"username": "admin", "password": "adminpass"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_login_wrong_password(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
    assert r.status_code == 200
    assert b"salah" in r.content.lower() or b"invalid" in r.content.lower()


@pytest.mark.asyncio
async def test_dashboard_requires_login(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


@pytest.mark.asyncio
async def test_admin_route_requires_admin(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "user1", "password": "userpass"})
        r = await client.get("/admin/users", follow_redirects=False)
    assert r.status_code == 403
```

- [ ] **Step 3: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_web_auth.py -v
```

- [ ] **Step 4: Buat `src/sn_forwarder/web/auth.py`**

```python
from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext

from ..store import UserRecord, UserStore

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_LOCKOUT_SECONDS = 300
_MAX_ATTEMPTS = 5


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def get_csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    return request.session["csrf_token"]


def verify_csrf(request: Request, form_token: str) -> bool:
    expected = request.session.get("csrf_token", "")
    return secrets.compare_digest(expected, form_token)


def is_brute_forced(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _failed_attempts[ip] if now - t < _LOCKOUT_SECONDS]
    _failed_attempts[ip] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def record_failed(ip: str) -> None:
    _failed_attempts[ip].append(time.time())


def login_user(request: Request, user_id: int) -> None:
    request.session["user_id"] = user_id


def logout_user(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request, user_store: UserStore) -> UserRecord | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return user_store.get_by_id(user_id)


def require_user(request: Request, user_store: UserStore) -> UserRecord:
    user = get_current_user(request, user_store)
    if user is None or not user.is_active:
        raise _redirect_to_login()
    return user


def require_admin(request: Request, user_store: UserStore) -> UserRecord:
    user = require_user(request, user_store)
    if user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 5: Buat `src/sn_forwarder/web/app.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from ..balance import BalanceService
from ..config import Settings
from ..store import ProductStore, RequestStore, UserStore
from ..worker import RegistrationWorker
from .auth import (
    get_csrf_token,
    is_brute_forced,
    login_user,
    logout_user,
    record_failed,
    require_admin,
    require_user,
    verify_password,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def build_web_app(
    settings: Settings,
    user_store: UserStore,
    product_store: ProductStore,
    request_store: RequestStore,
    balance_service: BalanceService,
    worker: RegistrationWorker | None,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Store dependencies on app state so routes can access them
    app.state.user_store = user_store
    app.state.product_store = product_store
    app.state.request_store = request_store
    app.state.balance_service = balance_service
    app.state.worker = worker
    app.state.templates = templates

    from .routes_panel import router as panel_router
    from .routes_admin import router as admin_router

    app.include_router(panel_router)
    app.include_router(admin_router, prefix="/admin")

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        csrf = get_csrf_token(request)
        return templates.TemplateResponse("login.html", {"request": request, "csrf_token": csrf, "error": None})

    @app.post("/login")
    async def login_post(request: Request):
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
        ip = request.client.host if request.client else "unknown"

        if is_brute_forced(ip):
            csrf = get_csrf_token(request)
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "csrf_token": csrf, "error": "Terlalu banyak percobaan. Tunggu 5 menit."},
                status_code=429,
            )

        user = user_store.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash) or not user.is_active:
            record_failed(ip)
            csrf = get_csrf_token(request)
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "csrf_token": csrf, "error": "Username atau password salah."},
                status_code=200,
            )

        login_user(request, user.id)
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.get("/logout")
    async def logout(request: Request):
        logout_user(request)
        return RedirectResponse(url="/login", status_code=302)

    return app
```

- [ ] **Step 6: Buat direktori templates dan static kosong**

```powershell
New-Item -ItemType Directory -Force src/sn_forwarder/web/templates/admin
New-Item -ItemType Directory -Force src/sn_forwarder/web/static
```

- [ ] **Step 7: Buat template placeholder sementara untuk bisa test**

Buat `src/sn_forwarder/web/templates/login.html`:

```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Login</title></head>
<body>
<h1>Login</h1>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post" action="/login">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <input name="username" placeholder="Username"><br>
  <input name="password" type="password" placeholder="Password"><br>
  <button type="submit">Login</button>
</form>
</body>
</html>
```

Buat `src/sn_forwarder/web/templates/base.html`:

```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>SN Panel</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<nav>
  <a href="/dashboard">Dashboard</a> |
  <a href="/order">Order</a> |
  <a href="/history">History</a> |
  <a href="/transactions">Transaksi</a>
  {% if user and user.role == 'admin' %} |
  <a href="/admin/users">Admin</a>
  {% endif %} |
  <a href="/logout">Logout</a>
</nav>
<main>{% block content %}{% endblock %}</main>
</body>
</html>
```

Buat `src/sn_forwarder/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Dashboard</h1>
<p>Selamat datang, <strong>{{ user.username }}</strong></p>
<p>Saldo: <strong>Rp {{ "{:,.0f}".format(user.balance) }}</strong></p>
<a href="/order"><button>Order Baru</button></a>
{% endblock %}
```

Buat stub routes agar app bisa import (task 7 & 8 akan isi ini):

Buat `src/sn_forwarder/web/routes_panel.py`:

```python
from fastapi import APIRouter
router = APIRouter()
```

Buat `src/sn_forwarder/web/routes_admin.py`:

```python
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 8: Run — pastikan test_web_auth PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_web_auth.py -v
```

Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add src/sn_forwarder/web/ tests/test_web_auth.py
git commit -m "feat: add FastAPI app factory, session auth, login/logout"
```

---

### Task 7: User Panel Routes + Templates

**Files:**
- Modify: `src/sn_forwarder/web/routes_panel.py`
- Modify: `src/sn_forwarder/web/templates/dashboard.html` (sudah ada)
- Create: `src/sn_forwarder/web/templates/order.html`
- Create: `src/sn_forwarder/web/templates/history.html`
- Create: `src/sn_forwarder/web/templates/transactions.html`
- Create: `tests/test_web_panel.py`

**Interfaces:**
- Consumes: `require_user`, `get_csrf_token`, `verify_csrf`, `ProductStore`, `RequestStore`, `BalanceService`, `RegistrationWorker.enqueue`, `RegistrationJob`
- Routes: `GET /dashboard`, `GET /order`, `POST /order`, `GET /history`, `GET /transactions`, `GET /api/request/{id}/status`

- [ ] **Step 1: Tulis failing test**

Buat `tests/test_web_panel.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sn_forwarder.balance import BalanceService
from sn_forwarder.config import Settings
from sn_forwarder.store import ProductStore, RequestStore, UserStore
from sn_forwarder.web.app import build_web_app
from sn_forwarder.web.auth import hash_password


def make_settings():
    return Settings(
        api_id=1, api_hash="h", target_bot_username="@b",
        reply_timeout_seconds=30.0, database_path=":memory:",
        telethon_session_name="s", session_secret="testsecret1234567890",
        web_host="127.0.0.1", web_port=8000,
    )


class FakeWorker:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, job):
        self.jobs.append(job)
        return len(self.jobs)


def make_app_with_balance(tmp_path, balance=100000):
    db = str(tmp_path / "db.sqlite3")
    settings = make_settings()
    user_store = UserStore(db)
    product_store = ProductStore(db)
    request_store = RequestStore(db)
    balance_service = BalanceService(db)
    worker = FakeWorker()

    uid = user_store.create_user("alice", hash_password("pass"), role="user")
    user_store._add_balance(uid, balance)
    product_store.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)

    app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker)
    return app, worker, user_store, request_store


async def login(client):
    await client.post("/login", data={"username": "alice", "password": "pass"})


@pytest.mark.asyncio
async def test_dashboard_shows_balance(tmp_path):
    app, *_ = make_app_with_balance(tmp_path, balance=75000)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/dashboard")
    assert r.status_code == 200
    assert b"75" in r.content  # saldo 75,000 muncul


@pytest.mark.asyncio
async def test_order_post_success(tmp_path):
    app, worker, user_store, request_store = make_app_with_balance(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/order")  # ambil csrf_token dari form
        # Ambil product_id dari halaman
        import re
        pid_match = re.search(rb'name="product_id"[^>]*value="(\d+)"', r.content)
        if not pid_match:
            pid_match = re.search(rb'value="(\d+)"[^>]*name="product_id"', r.content)
        csrf_match = re.search(rb'name="csrf_token" value="([^"]+)"', r.content)
        pid = pid_match.group(1).decode() if pid_match else "1"
        csrf = csrf_match.group(1).decode() if csrf_match else ""
        r2 = await client.post("/order", data={"product_id": pid, "sn": "SN999", "csrf_token": csrf}, follow_redirects=False)
    assert r2.status_code == 302
    assert len(worker.jobs) == 1
    assert worker.jobs[0].sn == "SN999"


@pytest.mark.asyncio
async def test_order_post_insufficient_balance(tmp_path):
    app, worker, *_ = make_app_with_balance(tmp_path, balance=0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/order")
        import re
        csrf_match = re.search(rb'name="csrf_token" value="([^"]+)"', r.content)
        csrf = csrf_match.group(1).decode() if csrf_match else ""
        r2 = await client.post("/order", data={"product_id": "1", "sn": "SN999", "csrf_token": csrf})
    assert len(worker.jobs) == 0
    assert b"saldo" in r2.content.lower()


@pytest.mark.asyncio
async def test_history_page(tmp_path):
    app, *_ = make_app_with_balance(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/history")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_status_api(tmp_path):
    app, worker, user_store, request_store = make_app_with_balance(tmp_path)
    db = str(tmp_path / "db.sqlite3")
    product_store = ProductStore(db)
    pid = product_store.list_active()[0].id
    uid = user_store.list_all()[0].id
    rid = request_store.create_order(uid, pid, "SN1", 50000)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get(f"/api/request/{rid}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
```

- [ ] **Step 2: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_web_panel.py -v
```

- [ ] **Step 3: Isi `src/sn_forwarder/web/routes_panel.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..worker import RegistrationJob
from .auth import get_csrf_token, require_user, verify_csrf

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = require_user(request, request.app.state.user_store)
    fresh = request.app.state.user_store.get_by_id(user.id)
    return request.app.state.templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": fresh}
    )


@router.get("/order", response_class=HTMLResponse)
async def order_page(request: Request):
    user = require_user(request, request.app.state.user_store)
    products = request.app.state.product_store.list_active()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        "order.html",
        {"request": request, "user": user, "products": products, "csrf_token": csrf, "error": None},
    )


@router.post("/order")
async def order_post(request: Request):
    user = require_user(request, request.app.state.user_store)
    form = await request.form()
    csrf = str(form.get("csrf_token", ""))
    if not verify_csrf(request, csrf):
        return RedirectResponse(url="/login", status_code=302)

    product_id = int(form.get("product_id", 0))
    sn = str(form.get("sn", "")).strip()

    product = request.app.state.product_store.get_by_id(product_id)
    if not product or not product.is_active:
        return _order_error(request, user, "Produk tidak valid.")

    if not sn:
        return _order_error(request, user, "SN tidak boleh kosong.")

    request_id = request.app.state.request_store.create_order(
        user.id, product.id, sn, product.price
    )
    if request_id is None:
        return _order_error(request, user, "Saldo tidak cukup. Hubungi admin untuk top-up.")

    job = RegistrationJob(
        request_id=request_id,
        user_id=user.id,
        product_id=product.id,
        sn=sn,
        button_label=product.button_label,
        price_charged=product.price,
    )
    await request.app.state.worker.enqueue(job)
    return RedirectResponse(url=f"/history?submitted={request_id}", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    user = require_user(request, request.app.state.user_store)
    rows = request.app.state.request_store.get_by_user(user.id, limit=50)
    submitted = request.query_params.get("submitted")
    return request.app.state.templates.TemplateResponse(
        "history.html", {"request": request, "user": user, "rows": rows, "submitted": submitted}
    )


@router.get("/transactions", response_class=HTMLResponse)
async def transactions(request: Request):
    user = require_user(request, request.app.state.user_store)
    fresh = request.app.state.user_store.get_by_id(user.id)
    txns = request.app.state.balance_service.get_transactions(user.id)
    return request.app.state.templates.TemplateResponse(
        "transactions.html", {"request": request, "user": fresh, "txns": txns}
    )


@router.get("/api/request/{request_id}/status")
async def request_status(request_id: int, request: Request):
    user = require_user(request, request.app.state.user_store)
    try:
        record = request.app.state.request_store.get_request(request_id)
    except KeyError:
        return JSONResponse({"error": "not found"}, status_code=404)
    if record.user_id != user.id and user.role != "admin":
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse({"status": record.status, "reply_text": record.reply_text, "error_text": record.error_text})


def _order_error(request: Request, user, message: str):
    products = request.app.state.product_store.list_active()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        "order.html",
        {"request": request, "user": user, "products": products, "csrf_token": csrf, "error": message},
        status_code=200,
    )
```

- [ ] **Step 4: Buat template order, history, transactions**

Buat `src/sn_forwarder/web/templates/order.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Order Baru</h1>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post" action="/order">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <label>Produk:
    <select name="product_id">
      {% for p in products %}
      <option value="{{ p.id }}">{{ p.name }} — Rp {{ "{:,.0f}".format(p.price) }}</option>
      {% endfor %}
    </select>
  </label><br>
  <label>Serial Number: <input name="sn" required></label><br>
  <button type="submit">Submit</button>
</form>
{% endblock %}
```

Buat `src/sn_forwarder/web/templates/history.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>History</h1>
{% if submitted %}
<p>Request #{{ submitted }} dikirim. Status akan update otomatis.</p>
<script>
  (function poll() {
    fetch('/api/request/{{ submitted }}/status')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'pending' || d.status === 'processing') {
          setTimeout(poll, 3000);
        } else {
          location.reload();
        }
      });
  })();
</script>
{% endif %}
<table border="1" cellpadding="6">
  <tr><th>#</th><th>Produk</th><th>SN</th><th>Status</th><th>Reply</th><th>Harga</th><th>Waktu</th></tr>
  {% for r in rows %}
  <tr id="row-{{ r.id }}">
    <td>{{ r.id }}</td>
    <td>{{ r.product_name }}</td>
    <td>{{ r.sn }}</td>
    <td>{{ r.status }}</td>
    <td>{{ r.reply_text or r.error_text or '-' }}</td>
    <td>Rp {{ "{:,.0f}".format(r.price_charged) }}</td>
    <td>{{ r.created_at }}</td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

Buat `src/sn_forwarder/web/templates/transactions.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Riwayat Transaksi</h1>
<p>Saldo saat ini: <strong>Rp {{ "{:,.0f}".format(user.balance) }}</strong></p>
<table border="1" cellpadding="6">
  <tr><th>#</th><th>Tipe</th><th>Jumlah</th><th>Saldo Setelah</th><th>Ref</th><th>Waktu</th></tr>
  {% for t in txns %}
  <tr>
    <td>{{ t.id }}</td>
    <td>{{ t.type }}</td>
    <td>Rp {{ "{:,.0f}".format(t.amount) }}</td>
    <td>Rp {{ "{:,.0f}".format(t.balance_after) }}</td>
    <td>{{ t.ref_request_id or '-' }}</td>
    <td>{{ t.created_at }}</td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 5: Run — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_web_panel.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/sn_forwarder/web/routes_panel.py src/sn_forwarder/web/templates/
git commit -m "feat: add user panel routes (dashboard, order, history, transactions)"
```

---

### Task 8: Admin Routes + Templates

**Files:**
- Modify: `src/sn_forwarder/web/routes_admin.py`
- Create: `src/sn_forwarder/web/templates/admin/users.html`
- Create: `src/sn_forwarder/web/templates/admin/products.html`
- Create: `src/sn_forwarder/web/templates/admin/history.html`
- Create: `tests/test_web_admin.py`

**Interfaces:**
- Consumes: `require_admin`, `UserStore`, `ProductStore`, `BalanceService`, `RequestStore`
- Routes: `GET /admin/users`, `POST /admin/users`, `POST /admin/users/{id}/toggle`, `POST /admin/users/{id}/topup`, `GET /admin/products`, `POST /admin/products`, `POST /admin/products/{id}`, `GET /admin/history`

- [ ] **Step 1: Tulis failing test**

Buat `tests/test_web_admin.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sn_forwarder.balance import BalanceService
from sn_forwarder.config import Settings
from sn_forwarder.store import ProductStore, RequestStore, UserStore
from sn_forwarder.web.app import build_web_app
from sn_forwarder.web.auth import hash_password


def make_settings():
    return Settings(
        api_id=1, api_hash="h", target_bot_username="@b",
        reply_timeout_seconds=30.0, database_path=":memory:",
        telethon_session_name="s", session_secret="testsecret1234567890",
        web_host="127.0.0.1", web_port=8000,
    )


def make_app(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    settings = make_settings()
    user_store = UserStore(db)
    product_store = ProductStore(db)
    request_store = RequestStore(db)
    balance_service = BalanceService(db)
    user_store.create_user("admin", hash_password("adminpass"), role="admin")
    user_store.create_user("user1", hash_password("upass"), role="user")
    app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker=None)
    return app, user_store, product_store, balance_service


async def admin_login(client):
    await client.post("/login", data={"username": "admin", "password": "adminpass"})


@pytest.mark.asyncio
async def test_admin_can_create_product(tmp_path):
    app, *_ = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await admin_login(client)
        r = await client.post("/admin/products", data={
            "name": "A12+", "button_label": "Amrr Activator Pro Tool A12+",
            "price": "50000", "sort_order": "0",
        }, follow_redirects=False)
    assert r.status_code == 302


@pytest.mark.asyncio
async def test_admin_topup_increases_balance(tmp_path):
    app, user_store, *_ = make_app(tmp_path)
    uid = user_store.get_by_username("user1").id
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await admin_login(client)
        r = await client.post(f"/admin/users/{uid}/topup", data={"amount": "100000"}, follow_redirects=False)
    assert r.status_code == 302
    assert user_store.get_by_id(uid).balance == 100000


@pytest.mark.asyncio
async def test_admin_toggle_user(tmp_path):
    app, user_store, *_ = make_app(tmp_path)
    uid = user_store.get_by_username("user1").id
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await admin_login(client)
        await client.post(f"/admin/users/{uid}/toggle", follow_redirects=False)
    assert user_store.get_by_id(uid).is_active == 0


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin(tmp_path):
    app, *_ = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "user1", "password": "upass"})
        r = await client.get("/admin/users")
    assert r.status_code == 403
```

- [ ] **Step 2: Run — pastikan FAIL**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_web_admin.py -v
```

- [ ] **Step 3: Isi `src/sn_forwarder/web/routes_admin.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth import get_csrf_token, require_admin

router = APIRouter()


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    require_admin(request, request.app.state.user_store)
    users = request.app.state.user_store.list_all()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        "admin/users.html", {"request": request, "users": users, "csrf_token": csrf}
    )


@router.post("/users")
async def admin_create_user(request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    from .auth import hash_password
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", "")).strip()
    role = str(form.get("role", "user")).strip()
    if username and password:
        request.app.state.user_store.create_user(username, hash_password(password), role=role)
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/toggle")
async def admin_toggle_user(user_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    user = request.app.state.user_store.get_by_id(user_id)
    if user:
        request.app.state.user_store.set_active(user_id, 0 if user.is_active else 1)
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/topup")
async def admin_topup(user_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    amount = int(form.get("amount", 0))
    if amount > 0:
        request.app.state.balance_service.topup(user_id, amount, note="topup admin")
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/products", response_class=HTMLResponse)
async def admin_products(request: Request):
    require_admin(request, request.app.state.user_store)
    products = request.app.state.product_store.list_all()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        "admin/products.html", {"request": request, "products": products, "csrf_token": csrf}
    )


@router.post("/products")
async def admin_create_product(request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    button_label = str(form.get("button_label", "")).strip()
    price = int(form.get("price", 0))
    sort_order = int(form.get("sort_order", 0))
    if name and button_label and price > 0:
        request.app.state.product_store.create_product(name, button_label, price, sort_order)
    return RedirectResponse(url="/admin/products", status_code=302)


@router.post("/products/{product_id}")
async def admin_update_product(product_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    button_label = str(form.get("button_label", "")).strip()
    price = int(form.get("price", 0))
    is_active = int(form.get("is_active", 1))
    sort_order = int(form.get("sort_order", 0))
    request.app.state.product_store.update(product_id, name, button_label, price, is_active, sort_order)
    return RedirectResponse(url="/admin/products", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def admin_history(request: Request):
    require_admin(request, request.app.state.user_store)
    rows = request.app.state.request_store.get_all(limit=100)
    return request.app.state.templates.TemplateResponse(
        "admin/history.html", {"request": request, "rows": rows}
    )
```

- [ ] **Step 4: Buat admin templates**

Buat `src/sn_forwarder/web/templates/admin/users.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Kelola User</h1>
<h2>Tambah User</h2>
<form method="post" action="/admin/users">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <input name="username" placeholder="Username" required>
  <input name="password" type="password" placeholder="Password" required>
  <select name="role"><option value="user">User</option><option value="admin">Admin</option></select>
  <button type="submit">Tambah</button>
</form>
<h2>Daftar User</h2>
<table border="1" cellpadding="6">
  <tr><th>ID</th><th>Username</th><th>Role</th><th>Saldo</th><th>Status</th><th>Aksi</th></tr>
  {% for u in users %}
  <tr>
    <td>{{ u.id }}</td>
    <td>{{ u.username }}</td>
    <td>{{ u.role }}</td>
    <td>Rp {{ "{:,.0f}".format(u.balance) }}</td>
    <td>{{ 'Aktif' if u.is_active else 'Nonaktif' }}</td>
    <td>
      <form method="post" action="/admin/users/{{ u.id }}/toggle" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button type="submit">{{ 'Nonaktifkan' if u.is_active else 'Aktifkan' }}</button>
      </form>
      <form method="post" action="/admin/users/{{ u.id }}/topup" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <input name="amount" type="number" placeholder="Nominal" style="width:100px">
        <button type="submit">Top-up</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

Buat `src/sn_forwarder/web/templates/admin/products.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Kelola Produk</h1>
<h2>Tambah Produk</h2>
<form method="post" action="/admin/products">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <input name="name" placeholder="Nama produk" required>
  <input name="button_label" placeholder="Teks tombol PERSIS di bot tujuan" required style="width:300px">
  <input name="price" type="number" placeholder="Harga (Rp)" required>
  <input name="sort_order" type="number" placeholder="Urutan" value="0">
  <button type="submit">Tambah</button>
</form>
<h2>Daftar Produk</h2>
<table border="1" cellpadding="6">
  <tr><th>ID</th><th>Nama</th><th>Button Label</th><th>Harga</th><th>Aktif</th><th>Urutan</th><th>Edit</th></tr>
  {% for p in products %}
  <tr>
    <td>{{ p.id }}</td>
    <td>{{ p.name }}</td>
    <td>{{ p.button_label }}</td>
    <td>Rp {{ "{:,.0f}".format(p.price) }}</td>
    <td>{{ 'Ya' if p.is_active else 'Tidak' }}</td>
    <td>{{ p.sort_order }}</td>
    <td>
      <form method="post" action="/admin/products/{{ p.id }}">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <input name="name" value="{{ p.name }}" style="width:100px">
        <input name="button_label" value="{{ p.button_label }}" style="width:200px">
        <input name="price" type="number" value="{{ p.price }}" style="width:80px">
        <select name="is_active"><option value="1" {% if p.is_active %}selected{% endif %}>Aktif</option><option value="0" {% if not p.is_active %}selected{% endif %}>Nonaktif</option></select>
        <input name="sort_order" type="number" value="{{ p.sort_order }}" style="width:50px">
        <button type="submit">Simpan</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

Buat `src/sn_forwarder/web/templates/admin/history.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>History Semua Request</h1>
<table border="1" cellpadding="6">
  <tr><th>#</th><th>User ID</th><th>Produk</th><th>SN</th><th>Status</th><th>Reply</th><th>Harga</th><th>Waktu</th></tr>
  {% for r in rows %}
  <tr>
    <td>{{ r.id }}</td>
    <td>{{ r.user_id }}</td>
    <td>{{ r.product_name }}</td>
    <td>{{ r.sn }}</td>
    <td>{{ r.status }}</td>
    <td>{{ r.reply_text or r.error_text or '-' }}</td>
    <td>Rp {{ "{:,.0f}".format(r.price_charged) }}</td>
    <td>{{ r.created_at }}</td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 5: Run — pastikan PASS**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_web_admin.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Run full suite**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest -q
```

Expected: semua pass.

- [ ] **Step 7: Commit**

```bash
git add src/sn_forwarder/web/routes_admin.py src/sn_forwarder/web/templates/admin/
git commit -m "feat: add admin routes (users, products, topup, history)"
```

---

### Task 9: Main.py Wiring + Admin Setup + CSS + README

**Files:**
- Modify: `src/sn_forwarder/main.py`
- Create: `src/sn_forwarder/setup_admin.py`
- Create: `src/sn_forwarder/web/static/style.css`
- Modify: `README.md`

**Interfaces:**
- Produces: `main()` — jalankan uvicorn + worker + telethon via `asyncio.gather`
- Produces: `python -m sn_forwarder.setup_admin` — buat akun admin pertama kali

- [ ] **Step 1: Tulis ulang `src/sn_forwarder/main.py`**

```python
from __future__ import annotations

import asyncio
import contextlib
import logging

import uvicorn
from telethon import TelegramClient

from .balance import BalanceService
from .config import load_settings
from .store import ProductStore, RequestStore, UserStore
from .target_client import TelethonTargetClient
from .web.app import build_web_app
from .worker import RegistrationWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def async_main() -> None:
    settings = load_settings()

    user_store = UserStore(settings.database_path)
    product_store = ProductStore(settings.database_path)
    request_store = RequestStore(settings.database_path)
    balance_service = BalanceService(settings.database_path)

    telethon_client = TelegramClient(
        settings.telethon_session_name,
        settings.api_id,
        settings.api_hash,
    )

    async with telethon_client:
        target_client = TelethonTargetClient(telethon_client, settings.target_bot_username)
        worker = RegistrationWorker(
            store=request_store,
            balance=balance_service,
            target_client=target_client,
            reply_timeout_seconds=settings.reply_timeout_seconds,
        )
        app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker)

        web_config = uvicorn.Config(
            app,
            host=settings.web_host,
            port=settings.web_port,
            log_level="warning",
        )
        web_server = uvicorn.Server(web_config)

        logger.info("Panel berjalan di http://%s:%s", settings.web_host, settings.web_port)
        logger.info("Tekan Ctrl+C untuk berhenti.")

        worker_task = asyncio.create_task(worker.run_forever())
        server_task = asyncio.create_task(web_server.serve())

        try:
            await asyncio.gather(worker_task, server_task)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutting down...")
        finally:
            worker_task.cancel()
            web_server.should_exit = True
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Buat `src/sn_forwarder/setup_admin.py`**

```python
"""Script satu kali untuk membuat akun admin pertama.

Jalankan: python -m sn_forwarder.setup_admin
"""
from __future__ import annotations

import getpass

from .config import load_settings
from .store import UserStore
from .web.auth import hash_password


def main() -> None:
    settings = load_settings()
    store = UserStore(settings.database_path)

    print("=== Setup Admin SN Forwarder ===")
    username = input("Username admin: ").strip()
    if not username:
        print("Username tidak boleh kosong.")
        return

    existing = store.get_by_username(username)
    if existing:
        print(f"User '{username}' sudah ada (role: {existing.role}).")
        return

    password = getpass.getpass("Password: ")
    if len(password) < 6:
        print("Password minimal 6 karakter.")
        return

    uid = store.create_user(username, hash_password(password), role="admin")
    print(f"Admin '{username}' berhasil dibuat (id={uid}).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Buat `src/sn_forwarder/web/static/style.css`**

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; font-size: 14px; background: #f5f5f5; color: #222; }
nav { background: #1a1a2e; color: #eee; padding: 10px 20px; }
nav a { color: #ccc; text-decoration: none; margin-right: 12px; }
nav a:hover { color: #fff; }
main { padding: 24px; max-width: 1100px; margin: 0 auto; }
h1 { font-size: 1.4rem; margin-bottom: 16px; }
h2 { font-size: 1.1rem; margin: 16px 0 8px; }
table { border-collapse: collapse; width: 100%; background: #fff; }
th, td { padding: 8px 10px; border: 1px solid #ddd; text-align: left; }
th { background: #f0f0f0; }
input, select { padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; }
button { padding: 6px 14px; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
button:hover { background: #2d2d5e; }
form { margin-bottom: 12px; }
p { margin-bottom: 10px; }
.error { color: #c00; }
```

- [ ] **Step 4: Update `.env` kamu — tambah field baru**

Buka `.env` dan tambahkan (sesuaikan dengan data kamu):

```
SESSION_SECRET=isi_dengan_string_acak_minimal_32_karakter
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

Hapus atau biarkan (tidak dipakai): `BOT_TOKEN`, `OWNER_USER_IDS`, `TARGET_COMMAND_TEMPLATE`.

- [ ] **Step 5: Hapus file database lama**

```powershell
Remove-Item -Force data\requests.sqlite3 -ErrorAction SilentlyContinue
```

Schema berubah total — file lama tidak kompatibel.

- [ ] **Step 6: Buat akun admin pertama**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m sn_forwarder.setup_admin
```

Ikuti prompt: masukkan username dan password admin.

- [ ] **Step 7: Smoke test import**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -c "from sn_forwarder.main import main; print('ok')"
```

Expected: `ok`

- [ ] **Step 8: Run full test suite**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest -q
```

Expected: semua pass.

- [ ] **Step 9: Update README.md**

Ganti isi `README.md`:

```markdown
# SN Forwarder Platform

Panel web multi-user untuk automasi registrasi SN lewat bot Telegram, berbasis saldo per user.

## Cara Kerja

1. User login ke panel web, pilih produk, masukkan SN.
2. Saldo user dipotong atomik. Request masuk antrian.
3. Aplikasi kirim `/placeorder` ke bot tujuan via akun Telegram owner (Telethon), klik tombol produk, kirim SN, tunggu reply.
4. Reply dikembalikan ke user di halaman history. Gagal/timeout → saldo dikembalikan otomatis.

## Setup Pertama Kali

### 1. Prerequisite
- Python 3.11+
- Akun Telegram (untuk Telethon) — login pertama kali perlu nomor HP + kode
- API ID & API Hash dari https://my.telegram.org

### 2. Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Konfigurasi

Copy `.env.example` → `.env`, isi semua field:

```
API_ID=           # dari my.telegram.org
API_HASH=         # dari my.telegram.org
TARGET_BOT_USERNAME=@username_bot_tujuan
REPLY_TIMEOUT_SECONDS=60
DATABASE_PATH=data/requests.sqlite3
TELETHON_SESSION_NAME=owner_session
SESSION_SECRET=   # string acak panjang, contoh: python -c "import secrets; print(secrets.token_hex(32))"
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

### 4. Buat akun admin

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m sn_forwarder.setup_admin
```

### 5. Jalankan

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m sn_forwarder.main
```

Pertama kali: Telethon minta nomor HP + kode login Telegram.
Selanjutnya: login otomatis dari session file.

Panel tersedia di: http://127.0.0.1:8000

### 6. Akses publik (opsional) — Cloudflare Tunnel

```powershell
# Install cloudflared dari https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
cloudflared tunnel --url http://127.0.0.1:8000
```

URL HTTPS publik akan muncul di terminal.

## Menambah Produk

Login sebagai admin → menu **Admin → Produk** → isi nama, button label (teks tombol PERSIS di bot tujuan), harga.

## Menambah User

Login sebagai admin → menu **Admin → Users** → isi username & password → top-up saldo.
```

- [ ] **Step 10: Commit final**

```bash
git add src/sn_forwarder/main.py src/sn_forwarder/setup_admin.py
git add src/sn_forwarder/web/static/style.css README.md .env.example
git commit -m "feat: wire main process, admin setup script, CSS, README"
```

---

## Self-Review

**Spec coverage:**
- ✅ Panel web multi-user: Task 6–8
- ✅ Admin kelola user (buat, aktif/nonaktif, top-up manual): Task 8
- ✅ Admin kelola produk (nama, button_label, harga, aktif): Task 8
- ✅ Saldo potong atomik saat submit: Task 2 (`create_order`)
- ✅ Refund otomatis gagal/timeout: Task 5 (worker)
- ✅ History request per user: Task 7
- ✅ Ledger transaksi per user: Task 7
- ✅ 3-step Telethon flow (placeorder→klik→SN): Task 4
- ✅ Satu proses asyncio (uvicorn+worker+telethon): Task 9
- ✅ Cloudflare Tunnel: README Task 9
- ✅ Hapus python-telegram-bot: Task 1
- ✅ WAL mode SQLite: Task 2
- ✅ bcrypt password: Task 6
- ✅ CSRF token: Task 6 + 7
- ✅ Brute-force lockout: Task 6
- ✅ Admin setup script: Task 9

**Type consistency:** `RegistrationJob` menggunakan `button_label` (Task 5), `send_and_wait(button_label, sn, timeout)` (Task 4), worker memanggil `send_and_wait(job.button_label, job.sn, ...)` (Task 5). Konsisten.

**Placeholder scan:** Tidak ada TBD/TODO. Semua kode lengkap.
