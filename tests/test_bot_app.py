from sn_forwarder.bot_app import is_authorized, parse_reg_text


def test_is_authorized_allows_owner():
    assert is_authorized(111, frozenset({111, 222})) is True


def test_is_authorized_rejects_missing_user():
    assert is_authorized(None, frozenset({111, 222})) is False


def test_parse_reg_text_extracts_sn():
    assert parse_reg_text("/reg SN123") == "SN123"


def test_parse_reg_text_requires_sn():
    assert parse_reg_text("/reg") is None

