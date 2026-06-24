# Telegram SN Forwarder Bot Design

## Goal

Build a local Windows-friendly Telegram bridge that lets an approved user send an SN registration request to our Telegram bot, forwards the request to another Telegram bot using the owner's Telegram account, waits for the target bot's reply, and sends that reply back to the original requester.

The first version is intended to run on the owner's PC, not on VPS or paid hosting.

## Architecture

The app is a single Python process with two Telegram clients:

- A normal Telegram Bot API client for the owner's bot. This receives commands from users or a panel.
- A Telethon user client for the owner's Telegram account. This sends commands to the target Telegram bot and receives its replies.

SQLite stores request logs and basic state. Configuration is loaded from `.env` so secrets are not committed.

## User Flow

1. An approved user sends `/reg <SN>` to the owner's bot.
2. The bot validates access and input format.
3. The app creates a request record with status `pending`.
4. The Telethon user client sends the configured command to the target bot, for example `/register <SN>`.
5. The app waits for a reply from the target bot.
6. The reply is matched to the pending request.
7. The owner's bot forwards the result back to the original requester.
8. The app updates the request log with `success`, `failed`, or `timeout`.

## Scope

Version 1 includes:

- `/start` health message.
- `/reg <SN>` request command.
- Admin/user whitelist by Telegram user ID.
- One-at-a-time request queue to avoid mismatched replies.
- Configurable target bot username.
- Configurable target command template.
- Timeout handling for missing replies.
- SQLite request logging.
- Local setup documentation for Windows.
- Telethon first-login helper flow.

Version 1 does not include:

- Web dashboard.
- Multi-account support.
- Paid hosting deployment.
- Complex menu automation in the target bot.
- Parallel request processing.

## Configuration

The app uses these environment variables:

- `BOT_TOKEN`: BotFather token for the owner's Telegram bot.
- `API_ID`: Telegram API ID for Telethon.
- `API_HASH`: Telegram API hash for Telethon.
- `OWNER_USER_IDS`: Comma-separated Telegram user IDs allowed to use the bot.
- `TARGET_BOT_USERNAME`: Username of the target registration bot.
- `TARGET_COMMAND_TEMPLATE`: Message template sent to the target bot, for example `/register {sn}`.
- `REPLY_TIMEOUT_SECONDS`: Maximum wait time before marking a request timed out.
- `DATABASE_PATH`: SQLite database path.
- `TELETHON_SESSION_NAME`: Telethon session filename or name.

## Data Flow

Incoming Telegram Bot API updates are handled by command handlers. Valid requests are passed into an async queue. A single worker consumes the queue, sends the prepared command through Telethon, waits for the next message from the target bot, stores the outcome, and notifies the original chat through the bot client.

The queue is intentionally serial in version 1. This keeps reply matching reliable even when the target bot does not include the SN in its response.

## Error Handling

- Unauthorized users receive an access denied message.
- Missing or malformed SN input receives usage guidance.
- If the target bot does not reply before the timeout, the original requester receives a timeout message.
- Telegram rate-limit errors are logged and reported as temporary failures.
- Unexpected exceptions are logged, the request is marked failed, and the requester gets a generic failure message.

## Local Operation

The owner runs the bot from a Windows terminal:

1. Install Python.
2. Create a virtual environment.
3. Install dependencies.
4. Copy `.env.example` to `.env`.
5. Fill in Telegram credentials and target bot settings.
6. Run the app once to authorize Telethon with the owner's phone number and login code.
7. Keep the terminal open while the bot is active.

The bot only works while the PC is powered on and connected to the internet.

## Testing

Verification should include:

- Config loading succeeds with required values.
- Unauthorized users are rejected.
- `/reg` without SN shows usage guidance.
- A valid request is queued and logged.
- A simulated timeout updates status and notifies the user.
- Manual end-to-end test against the real target bot after credentials are configured.

## Target Command

The default target command template is `/register {sn}`. The owner can change it in `.env` without code changes if the target Telegram bot uses a different command format.
