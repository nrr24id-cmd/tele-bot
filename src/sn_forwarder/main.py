from __future__ import annotations

import asyncio
import contextlib
import logging

from telethon import TelegramClient

from .bot_app import build_application
from .config import load_settings
from .store import RequestStore
from .target_client import TelethonTargetClient
from .worker import RegistrationWorker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def async_main() -> None:
    settings = load_settings()
    store = RequestStore(settings.database_path)

    telethon_client = TelegramClient(
        settings.telethon_session_name,
        settings.api_id,
        settings.api_hash,
    )

    async with telethon_client:
        target_client = TelethonTargetClient(telethon_client, settings.target_bot_username)
        worker = RegistrationWorker(settings, store, target_client, bot=None)
        app = build_application(settings, worker)
        worker.bot = app.bot

        worker_task = asyncio.create_task(worker.run_forever())
        try:
            await app.initialize()
            await app.start()
            if app.updater is None:
                raise RuntimeError("Telegram bot updater is not available")
            await app.updater.start_polling()
            logging.info("Bot is running. Press Ctrl+C to stop.")
            await asyncio.Event().wait()
        finally:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task
            if app.updater is not None and app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
            await app.shutdown()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
