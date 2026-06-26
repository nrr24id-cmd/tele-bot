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
