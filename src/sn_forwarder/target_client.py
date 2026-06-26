from __future__ import annotations

from typing import Protocol

from telethon import TelegramClient


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
            button_msg = await conv.get_response()
            await button_msg.click(text=button_label)
            await conv.send_message(sn)
            reply = await conv.get_response()
        return reply.raw_text or ""
