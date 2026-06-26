import re
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


class FakeWorker:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, job):
        self.jobs.append(job)
        return len(self.jobs)


def make_app(tmp_path, balance=100000):
    db = str(tmp_path / "db.sqlite3")
    settings = make_settings()
    user_store = UserStore(db)
    product_store = ProductStore(db)
    request_store = RequestStore(db)
    balance_service = BalanceService(db)
    worker = FakeWorker()
    uid = user_store.create_user("alice", hash_password("pass"), role="user")
    user_store._add_balance(uid, balance)
    product_store.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    app = build_web_app(settings, user_store, product_store, request_store, balance_service, worker)
    return app, worker, user_store, request_store, product_store


async def login(client):
    await client.post("/login", data={"username": "alice", "password": "pass"})


@pytest.mark.asyncio
async def test_dashboard_shows_balance(tmp_path):
    app, *_ = make_app(tmp_path, balance=75000)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/dashboard")
    assert r.status_code == 200
    assert b"75" in r.content


@pytest.mark.asyncio
async def test_order_post_success(tmp_path):
    app, worker, user_store, request_store, product_store = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/order")
        pid_match = re.search(rb'name="product_id"[^>]*value="(\d+)"|value="(\d+)"[^>]*name="product_id"', r.content)
        csrf_match = re.search(rb'name="csrf_token" value="([^"]+)"', r.content)
        pid = (pid_match.group(1) or pid_match.group(2)).decode() if pid_match else "1"
        csrf = csrf_match.group(1).decode() if csrf_match else ""
        r2 = await client.post("/order", data={"product_id": pid, "sn": "SN999", "csrf_token": csrf}, follow_redirects=False)
    assert r2.status_code == 302
    assert len(worker.jobs) == 1
    assert worker.jobs[0].sn == "SN999"


@pytest.mark.asyncio
async def test_order_post_insufficient_balance(tmp_path):
    app, worker, *_ = make_app(tmp_path, balance=0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/order")
        csrf_match = re.search(rb'name="csrf_token" value="([^"]+)"', r.content)
        csrf = csrf_match.group(1).decode() if csrf_match else ""
        r2 = await client.post("/order", data={"product_id": "1", "sn": "SN999", "csrf_token": csrf})
    assert len(worker.jobs) == 0
    assert b"saldo" in r2.content.lower()


@pytest.mark.asyncio
async def test_history_page(tmp_path):
    app, *_ = make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get("/history")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_status_api(tmp_path):
    app, worker, user_store, request_store, product_store = make_app(tmp_path)
    db = str(tmp_path / "db.sqlite3")
    pid = product_store.list_active()[0].id
    uid = user_store.list_all()[0].id
    rid = request_store.create_order(uid, pid, "SN1", 50000)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await login(client)
        r = await client.get(f"/api/request/{rid}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
