import pytest
from sn_forwarder.balance import BalanceService
from sn_forwarder.store import UserStore, ProductStore, RequestStore


def test_topup_increases_balance(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")

    balance.topup(uid, 100000, "manual topup")

    assert users.get_by_id(uid).balance == 100000


def test_topup_records_transaction(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")
    balance.topup(uid, 50000, "test")

    txns = balance.get_transactions(uid)
    assert len(txns) == 1
    assert txns[0].type == "topup"
    assert txns[0].amount == 50000
    assert txns[0].balance_after == 50000
    assert txns[0].note == "test"


def test_refund_increases_balance(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 200000)
    pid = products.create_product("A12+", "btn", 50000)
    rid = requests.create_order(uid, pid, "SN123", 50000)
    # after order: balance = 200000 - 50000 = 150000

    balance.refund(uid, 50000, ref_request_id=rid)
    # after refund: balance = 150000 + 50000 = 200000

    assert users.get_by_id(uid).balance == 200000


def test_refund_records_transaction(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)
    balance = BalanceService(db)
    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 200000)
    pid = products.create_product("A12+", "btn", 50000)
    rid = requests.create_order(uid, pid, "SN123", 50000)
    balance.refund(uid, 50000, ref_request_id=rid)

    txns = balance.get_transactions(uid)
    # Most recent transaction should be refund
    refund_txn = next((t for t in txns if t.type == "refund"), None)
    assert refund_txn is not None
    assert refund_txn.ref_request_id == rid
