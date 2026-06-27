# SN Forwarder Platform

Panel web multi-user untuk submit request ke bot Telegram via Telethon. Satu proses Python (FastAPI + Worker + Telethon) di PC lokal, diakses publik via Cloudflare Tunnel.

## Setup

### 1. Install dependensi

```bash
.venv/Scripts/pip install -r requirements.txt
```

### 2. Konfigurasi `.env`

Buat file `.env` di root project:

```
API_ID=12345
API_HASH=abcdef...
TARGET_BOT_USERNAME=@NamaBotTujuan
TELETHON_SESSION_NAME=owner_session
REPLY_TIMEOUT_SECONDS=60
SESSION_SECRET=string_acak_panjang_min32karakter
WEB_HOST=127.0.0.1
WEB_PORT=8000
DATABASE_PATH=sn_panel.db
```

Generate `SESSION_SECRET`:
```bash
.venv/Scripts/python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Buat admin pertama

```bash
PYTHONPATH=src .venv/Scripts/python -m sn_forwarder.setup_admin
```

### 4. Jalankan aplikasi

```bash
PYTHONPATH=src .venv/Scripts/python -m sn_forwarder.main
```

### 5. Akses publik via Cloudflare Tunnel

Di terminal terpisah:
```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

URL HTTPS muncul di terminal Cloudflare (mis. `https://xxxx.trycloudflare.com`).

## Penggunaan

- Admin login → `/admin/users` → tambah user + set saldo
- Admin → `/admin/products` → tambah produk (nama, button_label PERSIS di bot tujuan, harga)
- User login → `/order` → pilih produk, isi SN → submit
- Hasil muncul di `/history` (polling otomatis tiap 3 detik)
- Saldo dipotong saat submit; refund otomatis jika gagal/timeout

## Menjalankan tes

```bash
PYTHONPATH=src .venv/Scripts/python -m pytest -q
```
