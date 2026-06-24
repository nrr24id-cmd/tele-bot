from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import Settings
from .worker import RegistrationJob, RegistrationWorker


def is_authorized(user_id: int | None, owner_user_ids: frozenset[int]) -> bool:
    return user_id in owner_user_ids if user_id is not None else False


def parse_reg_text(text: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    return parts[1].strip()


def build_application(settings: Settings, worker: RegistrationWorker) -> Application:
    app = Application.builder().token(settings.bot_token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None:
            return
        await context.bot.send_message(update.effective_chat.id, "Bot register SN aktif.")

    async def reg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_chat is None or update.effective_message is None:
            return
        if not is_authorized(update.effective_user.id, settings.owner_user_ids):
            await context.bot.send_message(update.effective_chat.id, "Akses ditolak.")
            return
        sn = parse_reg_text(update.effective_message.text or "")
        if sn is None:
            await context.bot.send_message(update.effective_chat.id, "Format: /reg <SN>")
            return
        queue_size = await worker.enqueue(
            RegistrationJob(user_id=update.effective_user.id, chat_id=update.effective_chat.id, sn=sn)
        )
        await context.bot.send_message(update.effective_chat.id, f"Request diterima. Antrian: {queue_size}")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reg", reg))
    return app

