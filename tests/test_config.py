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
