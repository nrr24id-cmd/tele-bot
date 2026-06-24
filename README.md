# Telegram SN Forwarder Bot

Bot ini berjalan di PC Windows Anda. Bot menerima `/reg <SN>`, mengirim command register ke bot Telegram tujuan memakai akun Telegram Anda melalui Telethon, lalu mengirim reply bot tujuan kembali ke user atau panel.

## Cara Kerja

```text
User / Panel -> Bot Telegram Anda -> Queue lokal -> Akun Telegram Anda via Telethon -> Bot tujuan
Bot tujuan -> Akun Telegram Anda via Telethon -> Bot Telegram Anda -> User / Panel
```

Request diproses satu per satu supaya reply dari bot tujuan tidak tertukar.

## Setup Windows

1. Install Python 3.11 atau lebih baru dari https://www.python.org/downloads/windows/.
2. Buka PowerShell di folder project ini.
3. Buat virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Jika PowerShell menolak aktivasi script, jalankan:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Lalu ulangi aktivasi virtual environment.

4. Install dependency:

```powershell
python -m pip install -r requirements.txt
```

5. Copy `.env.example` menjadi `.env`.
6. Isi `.env`:

```text
BOT_TOKEN=token_dari_botfather
API_ID=api_id_dari_my_telegram_org
API_HASH=api_hash_dari_my_telegram_org
OWNER_USER_IDS=user_id_telegram_anda
TARGET_BOT_USERNAME=@username_bot_tujuan
TARGET_COMMAND_TEMPLATE=/register {sn}
REPLY_TIMEOUT_SECONDS=60
DATABASE_PATH=data/requests.sqlite3
TELETHON_SESSION_NAME=owner_session
```

## Mengambil Credential Telegram

- `BOT_TOKEN`: buat bot di BotFather, lalu copy token.
- `API_ID` dan `API_HASH`: login ke https://my.telegram.org, buka API development tools, lalu buat app.
- `OWNER_USER_IDS`: user ID Telegram yang boleh memakai bot. Anda bisa cek lewat bot seperti `@userinfobot`.
- `TARGET_BOT_USERNAME`: username bot Telegram tujuan, diawali `@`.

## Menjalankan Bot

Aktifkan virtual environment dulu:

```powershell
.\.venv\Scripts\Activate.ps1
```

Jalankan:

```powershell
$env:PYTHONPATH='src'
python -m sn_forwarder.main
```

Saat pertama kali berjalan, Telethon akan meminta nomor HP Telegram, kode login, dan password 2FA jika aktif. Setelah login berhasil, file `owner_session.session` dibuat lokal. Login berikutnya tidak perlu kode lagi selama file session tidak dihapus.

Bot hanya aktif selama terminal tetap terbuka, PC hidup, dan internet tersambung.

## Command

```text
/start
/reg SN123456
```

Jika bot tujuan memakai format lain, ubah `TARGET_COMMAND_TEMPLATE` di `.env`.

Contoh:

```text
TARGET_COMMAND_TEMPLATE=/reg {sn}
TARGET_COMMAND_TEMPLATE=REGISTER {sn}
```

## Data Lokal

- SQLite log request default: `data/requests.sqlite3`.
- Telethon session default: `owner_session.session`.
- `.env`, database, dan session file sudah masuk `.gitignore`.

Jangan kirim file `.env` atau `.session` ke orang lain karena bisa berisi akses akun.

## Troubleshooting

- `Akses ditolak.`: user ID pengirim belum masuk `OWNER_USER_IDS`.
- `Format: /reg <SN>`: command kurang SN.
- `Timeout: bot tujuan tidak membalas.`: bot tujuan lambat, tidak aktif, atau format command salah.
- `Gagal memproses request. Cek log aplikasi.`: lihat error di terminal PowerShell.

