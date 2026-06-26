import pytest
from httpx import ASGITransport, AsyncClient
from sn_forwarder.balance import BalanceService
from sn_forwarder.config import Settings
from sn_forwarder.store import ProductStore, RequestStore, UserStore
from sn_forwarder.web.app import build_web_app
from sn_forwarder.web.auth import hash_password


def make_settings():
    return Settings(
        api_id=1, api_hash="h", target_bot_username="@b",
        reply_timeout_seconds=30.0, database_path=":memory:",
        telethon_session_name="s", session_secret="testsecret1234567890",
        web_host="127.0.0.1", web_port=8000,
    )


def make_app(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    settings = make_settings()
    user_store = UserStore(db)
    product_store = ProductStore(db)
    request_store = RequestStore(db)
    balance_service = BalanceService(db)
    user_store.create_user("admin", hash_password("adminpass"), role="admin")
    user_store.create_user("user1", hash_password("userpass"), role="user")
    app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker=None)
    return app


@pytest.mark.asyncio
async def test_login_success(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/login", data={"username": "admin", "password": "adminpass"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_login_wrong_password(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
    assert r.status_code == 200
    assert b"salah" in r.content.lower()


@pytest.mark.asyncio
async def test_dashboard_requires_login(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


@pytest.mark.asyncio
async def test_admin_route_requires_admin(tmp_path):
    app = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "user1", "password": "userpass"})
        r = await client.get("/admin/users", follow_redirects=False)
    assert r.status_code == 403
