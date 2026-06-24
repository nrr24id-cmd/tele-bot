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

