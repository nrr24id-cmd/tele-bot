# Telegram SN Forwarder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Windows-friendly Python Telegram bridge that receives `/reg <SN>` requests, sends registration commands to a target Telegram bot through the owner's Telegram account, and returns the target reply to the requester.

**Architecture:** The app is a single async Python process. `python-telegram-bot` handles the owner's bot, Telethon handles the owner's user account, SQLite stores request history, and an async serial queue prevents mismatched target-bot replies.

**Tech Stack:** Python 3.11+, python-telegram-bot, Telethon, python-dotenv, pytest, pytest-asyncio, SQLite from the standard library.

## Global Constraints

- The first version runs locally on the owner's Windows PC.
- Secrets are loaded from `.env` and are not committed.
- The app uses a normal Telegram Bot API client for incoming user/panel commands.
- The app uses a Telethon user client for the owner's Telegram account.
- The request queue is one-at-a-time in version 1.
- The default target command template is `/register {sn}` and can be changed in `.env`.
- Version 1 excludes a web dashboard, multi-account support, paid hosting deployment, complex menu automation, and parallel request processing.

---

## File Structure

- Create: `.gitignore`
  - Keeps `.env`, Telethon session files, SQLite databases, caches, and virtualenv folders out of git.
- Create: `.env.example`
  - Documents all runtime configuration keys.
- Create: `requirements.txt`
  - Runtime and test dependencies.
- Create: `README.md`
  - Windows setup, BotFather/API credentials, Telethon login, and run instructions.
- Create: `src/sn_forwarder/__init__.py`
  - Package marker.
- Create: `src/sn_forwarder/config.py`
  - Loads and validates environment settings.
- Create: `src/sn_forwarder/store.py`
  - Creates SQLite schema and records request state transitions.
- Create: `src/sn_forwarder/target_client.py`
  - Wraps Telethon target-bot send/wait behavior behind a small interface.
- Create: `src/sn_forwarder/worker.py`
  - Owns the serial request queue and result processing.
- Create: `src/sn_forwarder/bot_app.py`
  - Registers `/start` and `/reg` Telegram bot handlers.
- Create: `src/sn_forwarder/main.py`
  - Wires config, store, Telethon client, queue worker, and Telegram bot app.
- Create: `tests/test_config.py`
  - Unit tests for config parsing and validation.
- Create: `tests/test_store.py`
  - Unit tests for SQLite request lifecycle.
- Create: `tests/test_worker.py`
  - Async tests for success and timeout queue processing.
- Create: `tests/test_bot_app.py`
  - Unit tests for authorization and `/reg` parsing helpers.

---

### Task 1: Project Scaffolding and Config

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `src/sn_forwarder/__init__.py`
- Create: `src/sn_forwarder/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` dataclass with fields `bot_token: str`, `api_id: int`, `api_hash: str`, `owner_user_ids: frozenset[int]`, `target_bot_username: str`, `target_command_template: str`, `reply_timeout_seconds: float`, `database_path: str`, `telethon_session_name: str`.
- Produces: `load_settings(env: Mapping[str, str] | None = None) -> Settings`.
- Produces: `Settings.render_target_command(sn: str) -> str`.

- [ ] **Step 1: Write failing config tests**

```python
# tests/test_config.py
import pytest

from sn_forwarder.config import ConfigError, load_settings


def valid_env():
    return {
        "BOT_TOKEN": "123:abc",
        "API_ID": "12345",
        "API_HASH": "hash",
        "OWNER_USER_IDS": "111,222",
        "TARGET_BOT_USERNAME": "@target_bot",
        "TARGET_COMMAND_TEMPLATE": "/register {sn}",
        "REPLY_TIMEOUT_SECONDS": "60",
        "DATABASE_PATH": "data/requests.sqlite3",
        "TELETHON_SESSION_NAME": "owner_session",
    }


def test_load_settings_parses_values():
    settings = load_settings(valid_env())

    assert settings.bot_token == "123:abc"
    assert settings.api_id == 12345
    assert settings.owner_user_ids == frozenset({111, 222})
    assert settings.target_bot_username == "@target_bot"
    assert settings.render_target_command("SN123") == "/register SN123"


def test_load_settings_rejects_missing_required_value():
    env = valid_env()
    env.pop("BOT_TOKEN")

    with pytest.raises(ConfigError, match="BOT_TOKEN"):
        load_settings(env)


def test_load_settings_rejects_template_without_sn_token():
    env = valid_env()
    env["TARGET_COMMAND_TEMPLATE"] = "/register"

    with pytest.raises(ConfigError, match="TARGET_COMMAND_TEMPLATE"):
        load_settings(env)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`

Expected: FAIL because `sn_forwarder.config` does not exist.

- [ ] **Step 3: Add scaffolding and config implementation**

```python
# src/sn_forwarder/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_id: int
    api_hash: str
    owner_user_ids: frozenset[int]
    target_bot_username: str
    target_command_template: str
    reply_timeout_seconds: float
    database_path: str
    telethon_session_name: str

    def render_target_command(self, sn: str) -> str:
        return self.target_command_template.format(sn=sn)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ

    bot_token = _required(env, "BOT_TOKEN")
    api_id = _parse_int(_required(env, "API_ID"), "API_ID")
    api_hash = _required(env, "API_HASH")
    owner_user_ids = _parse_user_ids(_required(env, "OWNER_USER_IDS"))
    target_bot_username = _required(env, "TARGET_BOT_USERNAME")
    target_command_template = env.get("TARGET_COMMAND_TEMPLATE", "/register {sn}").strip()
    if "{sn}" not in target_command_template:
        raise ConfigError("TARGET_COMMAND_TEMPLATE must include {sn}")
    reply_timeout_seconds = _parse_float(env.get("REPLY_TIMEOUT_SECONDS", "60"), "REPLY_TIMEOUT_SECONDS")
    database_path = env.get("DATABASE_PATH", "data/requests.sqlite3").strip()
    telethon_session_name = env.get("TELETHON_SESSION_NAME", "owner_session").strip()

    return Settings(
        bot_token=bot_token,
        api_id=api_id,
        api_hash=api_hash,
        owner_user_ids=owner_user_ids,
        target_bot_username=target_bot_username,
        target_command_template=target_command_template,
        reply_timeout_seconds=reply_timeout_seconds,
        database_path=database_path,
        telethon_session_name=telethon_session_name,
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


def _parse_user_ids(value: str) -> frozenset[int]:
    user_ids: set[int] = set()
    for raw_id in value.split(","):
        raw_id = raw_id.strip()
        if raw_id:
            user_ids.add(_parse_int(raw_id, "OWNER_USER_IDS"))
    if not user_ids:
        raise ConfigError("OWNER_USER_IDS must contain at least one Telegram user ID")
    return frozenset(user_ids)
```

- [ ] **Step 4: Add support files**

```text
# .gitignore
.env
*.session
*.session-journal
*.sqlite3
*.db
__pycache__/
.pytest_cache/
.venv/
venv/
data/
```

```text
# .env.example
BOT_TOKEN=123456:replace_me
API_ID=123456
API_HASH=replace_me
OWNER_USER_IDS=123456789
TARGET_BOT_USERNAME=@target_bot_username
TARGET_COMMAND_TEMPLATE=/register {sn}
REPLY_TIMEOUT_SECONDS=60
DATABASE_PATH=data/requests.sqlite3
TELETHON_SESSION_NAME=owner_session
```

```text
# requirements.txt
python-dotenv==1.0.1
python-telegram-bot==21.10
Telethon==1.38.1
pytest==8.3.4
pytest-asyncio==0.25.2
```

```python
# src/sn_forwarder/__init__.py
"""Telegram SN forwarder package."""
```

- [ ] **Step 5: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_config.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example requirements.txt src/sn_forwarder/__init__.py src/sn_forwarder/config.py tests/test_config.py
git commit -m "feat: add config loading"
```

---

### Task 2: SQLite Request Store

**Files:**
- Create: `src/sn_forwarder/store.py`
- Create: `tests/test_store.py`

**Interfaces:**
- Consumes: standard library `sqlite3`.
- Produces: `RequestRecord` dataclass.
- Produces: `RequestStore(database_path: str)`.
- Produces: `RequestStore.create_request(user_id: int, chat_id: int, sn: str, command: str) -> int`.
- Produces: `RequestStore.mark_sent(request_id: int) -> None`.
- Produces: `RequestStore.mark_success(request_id: int, reply_text: str) -> None`.
- Produces: `RequestStore.mark_failed(request_id: int, error_text: str) -> None`.
- Produces: `RequestStore.get_request(request_id: int) -> RequestRecord`.

- [ ] **Step 1: Write failing store tests**

```python
# tests/test_store.py
from sn_forwarder.store import RequestStore


def test_request_lifecycle(tmp_path):
    store = RequestStore(str(tmp_path / "requests.sqlite3"))

    request_id = store.create_request(
        user_id=111,
        chat_id=222,
        sn="SN123",
        command="/register SN123",
    )
    store.mark_sent(request_id)
    store.mark_success(request_id, "Register sukses")

    record = store.get_request(request_id)
    assert record.id == request_id
    assert record.user_id == 111
    assert record.chat_id == 222
    assert record.sn == "SN123"
    assert record.command == "/register SN123"
    assert record.status == "success"
    assert record.reply_text == "Register sukses"
    assert record.error_text is None


def test_mark_failed_records_error(tmp_path):
    store = RequestStore(str(tmp_path / "requests.sqlite3"))

    request_id = store.create_request(111, 222, "SN123", "/register SN123")
    store.mark_failed(request_id, "timeout")

    record = store.get_request(request_id)
    assert record.status == "failed"
    assert record.error_text == "timeout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_store.py -v`

Expected: FAIL because `sn_forwarder.store` does not exist.

- [ ] **Step 3: Implement store**

```python
# src/sn_forwarder/store.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_store.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/store.py tests/test_store.py
git commit -m "feat: add request store"
```

---

### Task 3: Target Client and Queue Worker

**Files:**
- Create: `src/sn_forwarder/target_client.py`
- Create: `src/sn_forwarder/worker.py`
- Create: `tests/test_worker.py`

**Interfaces:**
- Consumes: `RequestStore`.
- Produces: `TargetClientProtocol.send_and_wait(command: str, timeout_seconds: float) -> str`.
- Produces: `OutboundBotProtocol.send_message(chat_id: int, text: str) -> object`.
- Produces: `RegistrationJob(user_id: int, chat_id: int, sn: str)`.
- Produces: `RegistrationWorker.enqueue(job: RegistrationJob) -> int`.
- Produces: `RegistrationWorker.process_one(job: RegistrationJob) -> int`.

- [ ] **Step 1: Write failing worker tests**

```python
# tests/test_worker.py
import asyncio

import pytest

from sn_forwarder.store import RequestStore
from sn_forwarder.worker import RegistrationJob, RegistrationWorker


class FakeSettings:
    reply_timeout_seconds = 0.01

    def render_target_command(self, sn: str) -> str:
        return f"/register {sn}"


class FakeTargetClient:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.commands: list[str] = []

    async def send_and_wait(self, command: str, timeout_seconds: float) -> str:
        self.commands.append(command)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> object:
        self.messages.append((chat_id, text))
        return object()


@pytest.mark.asyncio
async def test_worker_sends_command_and_returns_reply(tmp_path):
    store = RequestStore(str(tmp_path / "requests.sqlite3"))
    target = FakeTargetClient("Register sukses")
    bot = FakeBot()
    worker = RegistrationWorker(FakeSettings(), store, target, bot)

    request_id = await worker.process_one(RegistrationJob(user_id=111, chat_id=222, sn="SN123"))

    assert target.commands == ["/register SN123"]
    assert bot.messages == [(222, "Register sukses")]
    assert store.get_request(request_id).status == "success"


@pytest.mark.asyncio
async def test_worker_reports_timeout(tmp_path):
    store = RequestStore(str(tmp_path / "requests.sqlite3"))
    target = FakeTargetClient(asyncio.TimeoutError())
    bot = FakeBot()
    worker = RegistrationWorker(FakeSettings(), store, target, bot)

    request_id = await worker.process_one(RegistrationJob(user_id=111, chat_id=222, sn="SN123"))

    assert bot.messages == [(222, "Timeout: bot tujuan tidak membalas.")]
    record = store.get_request(request_id)
    assert record.status == "failed"
    assert record.error_text == "timeout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_worker.py -v`

Expected: FAIL because `sn_forwarder.worker` does not exist.

- [ ] **Step 3: Implement target client protocol and worker**

```python
# src/sn_forwarder/target_client.py
from __future__ import annotations

import asyncio
from typing import Protocol

from telethon import TelegramClient, events


class TargetClientProtocol(Protocol):
    async def send_and_wait(self, command: str, timeout_seconds: float) -> str:
        ...


class TelethonTargetClient:
    def __init__(self, client: TelegramClient, target_bot_username: str) -> None:
        self.client = client
        self.target_bot_username = target_bot_username

    async def send_and_wait(self, command: str, timeout_seconds: float) -> str:
        target = await self.client.get_entity(self.target_bot_username)
        async with self.client.conversation(target, timeout=timeout_seconds) as conversation:
            await conversation.send_message(command)
            response = await conversation.get_response()
        return response.raw_text or ""
```

```python
# src/sn_forwarder/worker.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from .store import RequestStore
from .target_client import TargetClientProtocol

logger = logging.getLogger(__name__)


class SettingsProtocol(Protocol):
    reply_timeout_seconds: float

    def render_target_command(self, sn: str) -> str:
        ...


class OutboundBotProtocol(Protocol):
    async def send_message(self, chat_id: int, text: str) -> object:
        ...


@dataclass(frozen=True)
class RegistrationJob:
    user_id: int
    chat_id: int
    sn: str


class RegistrationWorker:
    def __init__(
        self,
        settings: SettingsProtocol,
        store: RequestStore,
        target_client: TargetClientProtocol,
        bot: OutboundBotProtocol,
    ) -> None:
        self.settings = settings
        self.store = store
        self.target_client = target_client
        self.bot = bot
        self.queue: asyncio.Queue[RegistrationJob] = asyncio.Queue()

    async def enqueue(self, job: RegistrationJob) -> int:
        await self.queue.put(job)
        return self.queue.qsize()

    async def run_forever(self) -> None:
        while True:
            job = await self.queue.get()
            try:
                await self.process_one(job)
            finally:
                self.queue.task_done()

    async def process_one(self, job: RegistrationJob) -> int:
        command = self.settings.render_target_command(job.sn)
        request_id = self.store.create_request(job.user_id, job.chat_id, job.sn, command)
        self.store.mark_sent(request_id)

        try:
            reply = await self.target_client.send_and_wait(command, self.settings.reply_timeout_seconds)
        except asyncio.TimeoutError:
            self.store.mark_failed(request_id, "timeout")
            await self.bot.send_message(job.chat_id, "Timeout: bot tujuan tidak membalas.")
        except Exception as exc:
            logger.exception("Registration request %s failed", request_id)
            self.store.mark_failed(request_id, str(exc))
            await self.bot.send_message(job.chat_id, "Gagal memproses request. Cek log aplikasi.")
        else:
            self.store.mark_success(request_id, reply)
            await self.bot.send_message(job.chat_id, reply or "Bot tujuan membalas tanpa teks.")

        return request_id
```

- [ ] **Step 4: Run worker tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_worker.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/target_client.py src/sn_forwarder/worker.py tests/test_worker.py
git commit -m "feat: add registration worker"
```

---

### Task 4: Telegram Bot Handlers

**Files:**
- Create: `src/sn_forwarder/bot_app.py`
- Create: `tests/test_bot_app.py`

**Interfaces:**
- Consumes: `RegistrationWorker.enqueue(job: RegistrationJob) -> int`.
- Produces: `is_authorized(user_id: int | None, owner_user_ids: frozenset[int]) -> bool`.
- Produces: `parse_reg_text(text: str) -> str | None`.
- Produces: `build_application(settings: Settings, worker: RegistrationWorker) -> telegram.ext.Application`.

- [ ] **Step 1: Write failing handler helper tests**

```python
# tests/test_bot_app.py
from sn_forwarder.bot_app import is_authorized, parse_reg_text


def test_is_authorized_allows_owner():
    assert is_authorized(111, frozenset({111, 222})) is True


def test_is_authorized_rejects_missing_user():
    assert is_authorized(None, frozenset({111, 222})) is False


def test_parse_reg_text_extracts_sn():
    assert parse_reg_text("/reg SN123") == "SN123"


def test_parse_reg_text_requires_sn():
    assert parse_reg_text("/reg") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_bot_app.py -v`

Expected: FAIL because `sn_forwarder.bot_app` does not exist.

- [ ] **Step 3: Implement bot handlers**

```python
# src/sn_forwarder/bot_app.py
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import Settings
from .worker import RegistrationJob, RegistrationWorker


def is_authorized(user_id: int | None, owner_user_ids: frozenset[int]) -> bool:
    return user_id in owner_user_ids if user_id is not None else False


def parse_reg_text(text: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    return parts[1].strip()


def build_application(settings: Settings, worker: RegistrationWorker) -> Application:
    app = Application.builder().token(settings.bot_token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None:
            return
        await context.bot.send_message(update.effective_chat.id, "Bot register SN aktif.")

    async def reg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_chat is None or update.effective_message is None:
            return
        if not is_authorized(update.effective_user.id, settings.owner_user_ids):
            await context.bot.send_message(update.effective_chat.id, "Akses ditolak.")
            return
        sn = parse_reg_text(update.effective_message.text or "")
        if sn is None:
            await context.bot.send_message(update.effective_chat.id, "Format: /reg <SN>")
            return
        queue_size = await worker.enqueue(
            RegistrationJob(user_id=update.effective_user.id, chat_id=update.effective_chat.id, sn=sn)
        )
        await context.bot.send_message(update.effective_chat.id, f"Request diterima. Antrian: {queue_size}")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reg", reg))
    return app
```

- [ ] **Step 4: Run handler tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_bot_app.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/bot_app.py tests/test_bot_app.py
git commit -m "feat: add bot command handlers"
```

---

### Task 5: Runtime Wiring and Documentation

**Files:**
- Create: `src/sn_forwarder/main.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `load_settings()`, `RequestStore`, `TelethonTargetClient`, `RegistrationWorker`, `build_application()`.
- Produces: `async_main() -> None`.
- Produces: CLI run command `python -m sn_forwarder.main`.

- [ ] **Step 1: Implement main runtime**

```python
# src/sn_forwarder/main.py
from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient

from .bot_app import build_application
from .config import load_settings
from .store import RequestStore
from .target_client import TelethonTargetClient
from .worker import RegistrationWorker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def async_main() -> None:
    settings = load_settings()
    store = RequestStore(settings.database_path)

    telethon_client = TelegramClient(
        settings.telethon_session_name,
        settings.api_id,
        settings.api_hash,
    )

    async with telethon_client:
        target_client = TelethonTargetClient(telethon_client, settings.target_bot_username)
        worker = RegistrationWorker(settings, store, target_client, bot=None)  # replaced after app is built
        app = build_application(settings, worker)
        worker.bot = app.bot

        worker_task = asyncio.create_task(worker.run_forever())
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            logging.info("Bot is running. Press Ctrl+C to stop.")
            await asyncio.Event().wait()
        finally:
            worker_task.cancel()
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add README**

```markdown
# Telegram SN Forwarder Bot

Bot ini berjalan di PC Windows Anda. Bot menerima `/reg <SN>`, mengirim command register ke bot Telegram tujuan memakai akun Telegram Anda melalui Telethon, lalu mengirim reply bot tujuan kembali ke user/panel.

## Setup

1. Install Python 3.11 atau lebih baru.
2. Buka PowerShell di folder project.
3. Buat virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Install dependency:

```powershell
python -m pip install -r requirements.txt
```

5. Copy `.env.example` menjadi `.env`.
6. Isi `.env`:

- `BOT_TOKEN` dari BotFather.
- `API_ID` dan `API_HASH` dari https://my.telegram.org.
- `OWNER_USER_IDS` dengan Telegram user ID Anda.
- `TARGET_BOT_USERNAME` dengan username bot tujuan.
- `TARGET_COMMAND_TEMPLATE` sesuai command bot tujuan, default `/register {sn}`.

## Menjalankan

```powershell
$env:PYTHONPATH='src'
python -m sn_forwarder.main
```

Saat pertama kali jalan, Telethon akan meminta nomor HP Telegram, kode login, dan password 2FA jika aktif. Setelah sukses, file session dibuat lokal dan login berikutnya tidak perlu kode lagi.

Bot hanya aktif selama terminal tetap terbuka, PC hidup, dan internet tersambung.

## Command

```text
/start
/reg SN123456
```

Jika bot tujuan memakai format lain, ubah `TARGET_COMMAND_TEMPLATE` di `.env`, misalnya:

```text
TARGET_COMMAND_TEMPLATE=/reg {sn}
```
```

- [ ] **Step 3: Run full automated tests**

Run: `$env:PYTHONPATH='src'; python -m pytest -v`

Expected: all tests PASS.

- [ ] **Step 4: Run import smoke test**

Run: `$env:PYTHONPATH='src'; python -c "from sn_forwarder.main import main; print('ok')"`

Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add src/sn_forwarder/main.py README.md
git commit -m "feat: wire local bot runtime"
```

---

## Self-Review

- Spec coverage: The plan covers local Windows operation, Bot API ingress, Telethon account egress, `.env` configuration, SQLite logging, serial queueing, timeout handling, whitelist checks, `/start`, `/reg <SN>`, and README setup.
- Scope check: Excluded items remain excluded: no dashboard, no hosting deployment, no multi-account support, no menu automation, no parallel processing.
- Placeholder scan: The plan uses concrete filenames, function names, config keys, commands, and expected results. The target command is configurable but defaults to `/register {sn}` as specified.
- Type consistency: `Settings`, `RequestStore`, `TelethonTargetClient`, `RegistrationWorker`, and `build_application` signatures are consistent across tasks.
