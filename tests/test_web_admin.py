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
    user_store.create_user("user1", hash_password("upass"), role="user")
    app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker=None)
    return app, user_store, product_store, balance_service


async def admin_login(client):
    await client.post("/login", data={"username": "admin", "password": "adminpass"})


@pytest.mark.asyncio
async def test_admin_can_create_product(tmp_path):
    app, *_ = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await admin_login(client)
        r = await client.post("/admin/products", data={
            "name": "A12+", "button_label": "Amrr Activator Pro Tool A12+",
            "price": "50000", "sort_order": "0",
        }, follow_redirects=False)
    assert r.status_code == 302


@pytest.mark.asyncio
async def test_admin_topup_increases_balance(tmp_path):
    app, user_store, *_ = make_app(tmp_path)
    uid = user_store.get_by_username("user1").id
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await admin_login(client)
        r = await client.post(f"/admin/users/{uid}/topup", data={"amount": "100000"}, follow_redirects=False)
    assert r.status_code == 302
    assert user_store.get_by_id(uid).balance == 100000


@pytest.mark.asyncio
async def test_admin_toggle_user(tmp_path):
    app, user_store, *_ = make_app(tmp_path)
    uid = user_store.get_by_username("user1").id
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await admin_login(client)
        await client.post(f"/admin/users/{uid}/toggle", follow_redirects=False)
    assert user_store.get_by_id(uid).is_active == 0


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin(tmp_path):
    app, *_ = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "user1", "password": "upass"})
        r = await client.get("/admin/users")
    assert r.status_code == 403
