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
        bot: OutboundBotProtocol | None,
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
            await self._send(job.chat_id, "Timeout: bot tujuan tidak membalas.")
        except Exception as exc:
            logger.exception("Registration request %s failed", request_id)
            self.store.mark_failed(request_id, str(exc))
            await self._send(job.chat_id, "Gagal memproses request. Cek log aplikasi.")
        else:
            self.store.mark_success(request_id, reply)
            await self._send(job.chat_id, reply or "Bot tujuan membalas tanpa teks.")

        return request_id

    async def _send(self, chat_id: int, text: str) -> None:
        if self.bot is None:
            raise RuntimeError("Outbound bot is not configured")
        await self.bot.send_message(chat_id, text)

