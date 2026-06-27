from __future__ import annotations

import asyncio
import logging

import uvicorn
from telethon import TelegramClient

from .balance import BalanceService
from .config import load_settings
from .store import ApiKeyStore, ProductStore, RequestStore, UserStore
from .target_client import TelethonTargetClient
from .web.app import build_web_app
from .worker import RegistrationWorker

_log_formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
_file_handler = logging.FileHandler("sn_panel.log", encoding="utf-8")
_file_handler.setFormatter(_log_formatter)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()

    user_store = UserStore(settings.database_path)
    product_store = ProductStore(settings.database_path)
    request_store = RequestStore(settings.database_path)
    balance_service = BalanceService(settings.database_path)
    api_key_store = ApiKeyStore(settings.database_path)

    telethon_client = TelegramClient(
        settings.telethon_session_name,
        settings.api_id,
        settings.api_hash,
    )
    await telethon_client.start()
    logger.info("Telethon connected")

    target_client = TelethonTargetClient(telethon_client, settings.target_bot_username)

    worker = RegistrationWorker(
        store=request_store,
        balance=balance_service,
        target_client=target_client,
        reply_timeout_seconds=settings.reply_timeout_seconds,
    )

    app = build_web_app(
        settings=settings,
        user_store=user_store,
        product_store=product_store,
        request_store=request_store,
        balance_service=balance_service,
        worker=worker,
        api_key_store=api_key_store,
    )

    uvicorn_config = uvicorn.Config(
        app,
        host=settings.web_host,
        port=settings.web_port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)

    logger.info("Starting SN Forwarder Platform on http://%s:%d", settings.web_host, settings.web_port)
    await asyncio.gather(
        server.serve(),
        worker.run_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
