#!/usr/bin/env python3
"""One-time script: create initial admin user."""
from __future__ import annotations

import getpass
import sys

from .config import load_settings
from .store import UserStore
from .web.auth import hash_password


def main() -> None:
    settings = load_settings()
    user_store = UserStore(settings.database_path)

    existing = user_store.list_all()
    if any(u.role == "admin" for u in existing):
        print("Admin sudah ada. Kelola user via panel /admin/users.")
        sys.exit(0)

    print("=== Setup Admin Pertama ===")
    username = input("Username admin: ").strip()
    if not username:
        print("Username tidak boleh kosong.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Konfirmasi password: ")
    if password != confirm:
        print("Password tidak cocok.")
        sys.exit(1)
    if len(password) < 8:
        print("Password minimal 8 karakter.")
        sys.exit(1)

    uid = user_store.create_user(username, hash_password(password), role="admin")
    print(f"Admin '{username}' (id={uid}) berhasil dibuat.")
    print("Jalankan: python -m sn_forwarder.main")


if __name__ == "__main__":
    main()
