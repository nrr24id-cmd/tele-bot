from __future__ import annotations

from typing import Protocol

from telethon import TelegramClient


class TargetClientProtocol(Protocol):
    async def send_and_wait(self, command: str, timeout_seconds: float) -> str:
        ...


class TelethonTargetClient:
    def __init__(self, client: TelegramClient, target_bot_username: str) -> None:
        self.client = client
        self.target_bot_username = target_bot_username

    async def send_and_wait(self, command: str, timeout_seconds: float) -> str:
        target = await self.client.get_entity(self.target_bot_username)
        async with self.client.conversation(target, timeout=timeout_seconds) as conversation:
            await conversation.send_message(command)
            response = await conversation.get_response()
        return response.raw_text or ""

