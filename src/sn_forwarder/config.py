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

    api_id = _parse_int(_required(env, "API_ID"), "API_ID")
    api_hash = _required(env, "API_HASH")
    target_bot_username = _required(env, "TARGET_BOT_USERNAME")
    reply_timeout_seconds = _parse_float(env.get("REPLY_TIMEOUT_SECONDS", "60"), "REPLY_TIMEOUT_SECONDS")
    database_path = env.get("DATABASE_PATH", "data/requests.sqlite3").strip()
    telethon_session_name = env.get("TELETHON_SESSION_NAME", "owner_session").strip()
    session_secret = _required(env, "SESSION_SECRET")
    web_host = env.get("WEB_HOST", "127.0.0.1").strip()
    web_port = _parse_int(env.get("WEB_PORT", "8000"), "WEB_PORT")

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        target_bot_username=target_bot_username,
        reply_timeout_seconds=reply_timeout_seconds,
        database_path=database_path,
        telethon_session_name=telethon_session_name,
        session_secret=session_secret,
        web_host=web_host,
        web_port=web_port,
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
