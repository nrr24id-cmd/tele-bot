from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext


class NotAuthenticatedException(Exception):
    """Raised when a route requires a logged-in user but none is found."""

from ..store import UserRecord, UserStore

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_LOCKOUT_SECONDS = 300
_MAX_ATTEMPTS = 5


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def get_csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    return request.session["csrf_token"]


def verify_csrf(request: Request, form_token: str) -> bool:
    expected = request.session.get("csrf_token", "")
    return secrets.compare_digest(expected, form_token)


def is_brute_forced(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _failed_attempts[ip] if now - t < _LOCKOUT_SECONDS]
    _failed_attempts[ip] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def record_failed(ip: str) -> None:
    _failed_attempts[ip].append(time.time())


def login_user(request: Request, user_id: int) -> None:
    request.session["user_id"] = user_id


def logout_user(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request, user_store: UserStore) -> UserRecord | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return user_store.get_by_id(user_id)


def require_user(request: Request, user_store: UserStore) -> UserRecord:
    user = get_current_user(request, user_store)
    if user is None or not user.is_active:
        raise NotAuthenticatedException()
    return user


def require_admin(request: Request, user_store: UserStore) -> UserRecord:
    user = require_user(request, user_store)
    if user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin only")
    return user
