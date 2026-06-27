from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from telethon import TelegramClient

logger = logging.getLogger(__name__)


class TargetClientProtocol(Protocol):
    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        ...


class TelethonTargetClient:
    def __init__(self, client: TelegramClient, target_bot_username: str) -> None:
        self.client = client
        self.target_bot_username = target_bot_username

    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        target = await self.client.get_entity(self.target_bot_username)
        async with self.client.conversation(target, timeout=timeout_seconds) as conv:
            await conv.send_message("/placeorder")
            logger.info("[TC] Sent /placeorder")

            button_msg = await conv.get_response()
            logger.info("[TC] Step1 response: %r", button_msg.raw_text)

            # Cari tombol dengan strip whitespace (bot mungkin punya trailing space)
            matched_btn = None
            if button_msg.buttons:
                for row in button_msg.buttons:
                    for btn in row:
                        logger.info("[TC] Found button: %r", btn.text)
                        if btn.text.strip() == button_label.strip():
                            matched_btn = btn
            if matched_btn is None:
                raise ValueError(f"Tombol '{button_label}' tidak ditemukan di menu bot")
            await matched_btn.click()
            logger.info("[TC] Clicked button: %r", matched_btn.text)

            # Bot tidak kirim pesan baru setelah klik — tunggu sebentar supaya callback diproses
            await asyncio.sleep(1.5)

            await conv.send_message(sn)
            logger.info("[TC] Sent SN: %r", sn)

            first = await conv.get_response()
            logger.info("[TC] Reply 1: %r", first.raw_text)

            # Bot kirim "Placing order..." dulu, lalu hasil asli di pesan kedua
            if first.raw_text and first.raw_text.startswith("Placing order"):
                second = await conv.get_response()
                logger.info("[TC] Reply 2: %r", second.raw_text)
                reply = second
            else:
                reply = first

        return reply.raw_text or ""
