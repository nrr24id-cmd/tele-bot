from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from ..balance import BalanceService
from ..config import Settings
from ..store import ProductStore, RequestStore, UserStore
from .auth import (
    NotAuthenticatedException,
    get_csrf_token,
    is_brute_forced,
    login_user,
    logout_user,
    record_failed,
    require_admin,
    require_user,
    verify_password,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def build_web_app(
    settings: Settings,
    user_store: UserStore,
    product_store: ProductStore,
    request_store: RequestStore,
    balance_service: BalanceService,
    worker,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    (TEMPLATES_DIR / "admin").mkdir(exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.state.user_store = user_store
    app.state.product_store = product_store
    app.state.request_store = request_store
    app.state.balance_service = balance_service
    app.state.worker = worker
    app.state.templates = templates

    from .routes_panel import router as panel_router
    from .routes_admin import router as admin_router

    app.include_router(panel_router)
    app.include_router(admin_router, prefix="/admin")

    @app.exception_handler(NotAuthenticatedException)
    async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException) -> Response:
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        csrf = get_csrf_token(request)
        return templates.TemplateResponse(request, "login.html", {"csrf_token": csrf, "error": None})

    @app.post("/login")
    async def login_post(request: Request):
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
        ip = request.client.host if request.client else "unknown"

        if is_brute_forced(ip):
            csrf = get_csrf_token(request)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"csrf_token": csrf, "error": "Terlalu banyak percobaan. Tunggu 5 menit."},
                status_code=429,
            )

        user = user_store.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash) or not user.is_active:
            record_failed(ip)
            csrf = get_csrf_token(request)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"csrf_token": csrf, "error": "Username atau password salah."},
                status_code=200,
            )

        login_user(request, user.id)
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.get("/logout")
    async def logout(request: Request):
        logout_user(request)
        return RedirectResponse(url="/login", status_code=302)

    return app
