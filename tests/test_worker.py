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

