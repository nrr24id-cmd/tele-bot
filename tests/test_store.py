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

