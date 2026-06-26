# SN Forwarder Platform — MVP Design (Fase 1)

**Tanggal:** 2026-06-26
**Scope:** Panel web multi-user dengan saldo, multi-produk, history request, semua satu proses di PC lokal + Cloudflare Tunnel.

---

## Batas Scope

**Termasuk di MVP:**
- Panel web (login sesi cookie)
- Admin kelola user (buat, aktifkan/nonaktifkan, top-up saldo manual)
- Admin kelola produk (tambah/edit/aktifkan, set harga, set `button_label`)
- Saldo per user: potong saat submit, refund otomatis saat gagal/timeout
- Submit request: pilih produk → masukkan SN → antrian serial → hasil via Telethon
- History request per user (admin lihat semua)
- Ledger transaksi per user (topup / debit / refund)
- Satu proses asyncio: FastAPI + Worker + Telethon berjalan bersamaan
- Cloudflare Tunnel untuk HTTPS publik tanpa VPS

**Ditunda (Fase 2):**
- DHRU Supplier API (endpoint kompatibel DHRU Fusion untuk panel lain)
- Payment gateway otomatis
- Multi-akun Telethon / paralel processing
- Bot Telegram `/reg` (dihapus di MVP, bisa ditambah kembali nanti)

---

## Arsitektur

Satu proses Python asyncio yang berjalan di PC lokal. Cloudflare Tunnel menyediakan URL HTTPS publik yang mengarah ke port FastAPI lokal.

```
Browser User
    │
    ▼
Cloudflare Tunnel (HTTPS publik)
    │
    ▼
FastAPI (panel web + Jinja2 templates)
    │  BalanceService.debit_atomic()
    │  RequestStore.create_request()
    ▼
RegistrationWorker (asyncio.Queue, serial)
    │  TelethonTargetClient.send_and_wait()
    ▼
Telethon (akun user owner)
    │  /placeorder → klik tombol → kirim SN → get_response()
    ▼
Bot Tujuan (@AmrrActivator dll.)
    │
    ▼  reply text
RegistrationWorker
    ├── sukses → RequestStore.mark_success() + simpan reply
    └── gagal/timeout → RequestStore.mark_failed() + BalanceService.refund()
```

**Prinsip utama:**
- Worker, store, dan Telethon netral terhadap asal request — siap untuk DHRU API di Fase 2 tanpa ubah core
- Semua I/O database lewat connection baru per operasi (SQLite WAL mode untuk concurrency FastAPI + worker)
- `python-telegram-bot` tidak digunakan — dependensi bisa dilepas dari `requirements.txt`

---

## Komponen dan File

```
src/sn_forwarder/
├── config.py              # diperluas: PRICE default dihapus, tambah WEB_HOST/PORT/SESSION_SECRET
├── store.py               # diperluas: users, products, requests (revisi kolom), transactions
├── balance.py             # BalanceService: debit_atomic, refund, topup, ledger
├── target_client.py       # TelethonTargetClient: alur 3 langkah (placeorder→klik→SN)
├── worker.py              # RegistrationWorker: terima job multi-origin, refund on fail
├── main.py                # asyncio.gather(uvicorn, worker.run_forever, telethon)
└── web/
    ├── app.py             # FastAPI factory, session middleware, Jinja2
    ├── auth.py            # login/logout, get_current_user, require_role
    ├── routes_panel.py    # /dashboard, /order, /history (user)
    ├── routes_admin.py    # /admin/users, /admin/products, /admin/topup
    ├── templates/
    │   ├── base.html
    │   ├── login.html
    │   ├── dashboard.html
    │   ├── order.html
    │   ├── history.html
    │   └── admin/
    │       ├── users.html
    │       ├── products.html
    │       └── topup.html
    └── static/
        └── style.css
```

---

## Model Data (SQLite)

Semua uang disimpan sebagai integer (rupiah). WAL mode diaktifkan saat init.

### `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,     -- bcrypt
    role TEXT NOT NULL DEFAULT 'user', -- 'admin' | 'user'
    balance INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### `products`
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,              -- nama tampil di panel
    button_label TEXT NOT NULL,      -- teks tombol PERSIS di bot tujuan
    price INTEGER NOT NULL,          -- harga dalam rupiah
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### `requests` (revisi dari store lama)
```sql
CREATE TABLE requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    sn TEXT NOT NULL,
    status TEXT NOT NULL,            -- 'pending'|'processing'|'success'|'failed'
    reply_text TEXT,
    error_text TEXT,
    price_charged INTEGER NOT NULL,  -- snapshot harga saat submit
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### `transactions`
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type TEXT NOT NULL,              -- 'topup'|'debit'|'refund'
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    ref_request_id INTEGER REFERENCES requests(id),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## Alur Submit Request

### 1. Cek dan potong saldo (atomik)
```sql
UPDATE users
SET balance = balance - :price
WHERE id = :user_id
  AND is_active = 1
  AND balance >= :price
```
Kalau 0 baris terdampak → tolak dengan "saldo tidak cukup" atau "akun tidak aktif". Tidak perlu SELECT terpisah — atomik mencegah race condition.

### 2. Catat transaksi debit dan request
Insert ke `transactions` (type='debit') dan `requests` (status='pending') dalam transaksi DB yang sama dengan langkah 1 (satu `BEGIN...COMMIT`).

### 3. Enqueue ke worker
`worker.enqueue(RegistrationJob(request_id, user_id, product_id, sn, button_label))`

### 4. Worker: kirim ke bot tujuan (Telethon 3 langkah)
```python
await conversation.send_message("/placeorder")
msg = await conversation.get_response()       # pesan berisi tombol
await msg.click(text=button_label)            # klik tombol produk
await conversation.send_message(sn)
reply = await conversation.get_response()     # hasil dari bot tujuan
```

### 5. Hasil
- **Sukses:** `mark_success(request_id, reply.raw_text)` → saldo tetap terpotong
- **Gagal/timeout:** `mark_failed(request_id, error)` → `BalanceService.refund(user_id, price, request_id)` (update balance + insert transaksi type='refund')

### 6. UI polling status
Panel halaman history atau dashboard polling `GET /api/request/{id}/status` setiap 3 detik sampai status bukan 'pending'/'processing'. Tidak perlu WebSocket untuk skala ini.

---

## Antarmuka Web

### Halaman User
| Route | Deskripsi |
|-------|-----------|
| `GET /login` | Form login |
| `POST /login` | Proses login, set sesi cookie |
| `GET /logout` | Hapus sesi |
| `GET /dashboard` | Saldo terkini + shortcut order |
| `GET /order` | Form: pilih produk (dropdown), isi SN, lihat harga |
| `POST /order` | Submit request, redirect ke history dengan flash status |
| `GET /history` | Tabel request milik user (paginated, 20/hal) |
| `GET /transactions` | Ledger saldo user |

### Halaman Admin
| Route | Deskripsi |
|-------|-----------|
| `GET /admin/users` | Daftar semua user + saldo + status aktif |
| `POST /admin/users` | Buat user baru (set password, role) |
| `POST /admin/users/{id}/toggle` | Aktifkan/nonaktifkan user |
| `POST /admin/users/{id}/topup` | Tambah saldo manual |
| `GET /admin/products` | Daftar produk |
| `POST /admin/products` | Tambah produk |
| `POST /admin/products/{id}` | Edit produk (nama, button_label, harga, aktif) |
| `GET /admin/history` | Semua request semua user |

### Endpoint JSON (untuk polling UI)
| Route | Deskripsi |
|-------|-----------|
| `GET /api/request/{id}/status` | Return `{"status": "...", "reply_text": "..."}` |

---

## Autentikasi dan Keamanan

- Password di-hash dengan **bcrypt** (via `passlib`)
- Sesi via signed cookie (`itsdangerous.URLSafeTimedSerializer`, `SESSION_SECRET` dari `.env`)
- Semua route non-publik cek `get_current_user()` → redirect ke `/login` kalau tidak ada sesi
- Route `/admin/*` cek `role == 'admin'` → 403 kalau bukan
- Token CSRF pada semua form POST (double-submit cookie pattern atau `itsdangerous`)
- Brute-force protection login: lockout 5 menit setelah 5 gagal (in-memory counter, cukup untuk skala ini)
- Cloudflare Tunnel menangani HTTPS — tidak perlu SSL cert di app

---

## Konfigurasi `.env` (Tambahan)

```
# Sudah ada:
API_ID=
API_HASH=
TELETHON_SESSION_NAME=owner_session

# Baru:
SESSION_SECRET=ganti_dengan_string_acak_panjang
WEB_HOST=127.0.0.1
WEB_PORT=8000
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=   # di-generate saat first-run
```

`BOT_TOKEN`, `OWNER_USER_IDS`, `TARGET_BOT_USERNAME`, `TARGET_COMMAND_TEMPLATE`, `REPLY_TIMEOUT_SECONDS` dari config lama **dihapus** karena bot Telegram ingress tidak digunakan di MVP ini.

---

## Dependensi (Tambahan ke `requirements.txt`)

```
fastapi==0.115.x
uvicorn[standard]==0.30.x
jinja2==3.1.x
python-multipart==0.0.x   # form parsing
passlib[bcrypt]==1.7.x
itsdangerous==2.1.x        # signed cookies + CSRF
```

Dihapus: `python-telegram-bot`

---

## Error Handling

| Kondisi | Penanganan |
|---------|-----------|
| Saldo kurang | Tolak sebelum enqueue, tampilkan pesan + saldo saat ini |
| User nonaktif | Tolak, tampilkan pesan |
| Bot tujuan timeout | mark_failed + refund otomatis, user lihat di history |
| Tombol produk tidak ditemukan di bot tujuan | Tangkap exception Telethon, mark_failed + refund |
| Bot tujuan tidak ada di server | Tangkap FloodWaitError/UserNotParticipantError, mark_failed + refund |
| Worker crash | Exception di `process_one` di-log, `run_forever` lanjut ke job berikutnya |
| Duplikat submit | Tidak ada deduplikasi di MVP — user bertanggung jawab |

---

## Testing

Gaya TDD yang sama dengan proyek yang sudah ada (pytest + pytest-asyncio).

| Modul | Test yang ditulis |
|-------|------------------|
| `balance.py` | debit_atomic sukses, saldo kurang ditolak, refund menambah saldo, topup, insert ledger |
| `store.py` (revisi) | lifecycle request baru (pending→success, pending→failed), get_by_user |
| `target_client.py` | Mock Telethon conversation 3 langkah (sukses, tombol tidak ketemu, timeout) |
| `worker.py` | Sukses → saldo tetap terpotong; gagal → refund dipanggil; exception worker tidak hentikan loop |
| `web/auth.py` | Login benar/salah, sesi valid, brute-force lockout |
| `web/routes_panel.py` | Order memotong saldo, saldo kurang ditolak (TestClient), polling status |
| `web/routes_admin.py` | Topup menambah saldo + ledger, non-admin ditolak 403 |

---

## Deployment (PC Lokal)

```powershell
# 1. Install dependensi baru
.\.venv\Scripts\pip install -r requirements.txt

# 2. Update .env (tambah SESSION_SECRET, WEB_HOST, WEB_PORT)

# 3. Jalankan app (bot + web + worker)
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m sn_forwarder.main

# 4. Jalankan Cloudflare Tunnel (terminal terpisah)
cloudflared tunnel --url http://127.0.0.1:8000

# 5. Akses panel via URL dari Cloudflare (mis. https://xxxx.trycloudflare.com)
```

---

## Fase 2 — DHRU Supplier API (Setelah MVP Stabil)

Worker sudah netral terhadap asal request. Fase 2 tinggal tambah:
- `web/routes_dhru.py` — endpoint kompatibel format DHRU Fusion (XML/JSON)
- `api_keys` table — API key per user
- Middleware autentikasi API key
- Mapping field DHRU ↔ field internal (product_id, SN)

Core worker, balance, store, dan Telethon tidak perlu diubah.
