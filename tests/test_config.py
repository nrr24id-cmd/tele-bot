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

