import asyncio
import pytest
from sn_forwarder.balance import BalanceService
from sn_forwarder.store import ProductStore, RequestStore, UserStore
from sn_forwarder.worker import RegistrationJob, RegistrationWorker


class FakeTargetClient:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    async def send_and_wait(self, button_label: str, sn: str, timeout_seconds: float) -> str:
        self.calls.append((button_label, sn))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def make_worker(tmp_path, reply: str | Exception = "OK"):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 200000)
    pid = products.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    store = RequestStore(db)
    balance = BalanceService(db)
    rid = store.create_order(uid, pid, "SN123", 50000)
    job = RegistrationJob(
        request_id=rid,
        user_id=uid,
        product_id=pid,
        sn="SN123",
        button_label="Amrr Activator Pro Tool A12+",
        price_charged=50000,
    )
    target = FakeTargetClient(reply)
    worker = RegistrationWorker(store, balance, target, reply_timeout_seconds=5.0)
    return worker, job, store, users, uid


@pytest.mark.asyncio
async def test_worker_success(tmp_path):
    worker, job, store, users, uid = make_worker(tmp_path, "Aktivasi berhasil")
    await worker.process_one(job)
    assert store.get_request(job.request_id).status == "success"
    assert store.get_request(job.request_id).reply_text == "Aktivasi berhasil"
    assert users.get_by_id(uid).balance == 150000  # saldo tidak dikembalikan


@pytest.mark.asyncio
async def test_worker_timeout_refunds(tmp_path):
    worker, job, store, users, uid = make_worker(tmp_path, asyncio.TimeoutError())
    await worker.process_one(job)
    assert store.get_request(job.request_id).status == "failed"
    assert users.get_by_id(uid).balance == 200000  # saldo dikembalikan


@pytest.mark.asyncio
async def test_worker_error_refunds(tmp_path):
    worker, job, store, users, uid = make_worker(tmp_path, RuntimeError("koneksi gagal"))
    await worker.process_one(job)
    assert store.get_request(job.request_id).status == "failed"
    assert users.get_by_id(uid).balance == 200000


@pytest.mark.asyncio
async def test_worker_enqueue_returns_qsize(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    store = RequestStore(db)
    balance = BalanceService(db)
    worker = RegistrationWorker(store, balance, FakeTargetClient("ok"), reply_timeout_seconds=5.0)
    job = RegistrationJob(1, 1, 1, "SN", "btn", 50000)
    size = await worker.enqueue(job)
    assert size == 1
