import pytest
from sn_forwarder.store import ProductStore, RequestStore, UserStore


def test_user_store_create_and_get(tmp_path):
    store = UserStore(str(tmp_path / "db.sqlite3"))
    uid = store.create_user("alice", "hash_abc", role="user")
    user = store.get_by_username("alice")
    assert user is not None
    assert user.id == uid
    assert user.role == "user"
    assert user.balance == 0
    assert user.is_active == 1


def test_user_store_duplicate_username_raises(tmp_path):
    store = UserStore(str(tmp_path / "db.sqlite3"))
    store.create_user("alice", "hash")
    with pytest.raises(Exception):
        store.create_user("alice", "hash2")


def test_user_store_set_active(tmp_path):
    store = UserStore(str(tmp_path / "db.sqlite3"))
    uid = store.create_user("alice", "hash")
    store.set_active(uid, 0)
    assert store.get_by_id(uid).is_active == 0


def test_product_store_create_and_list(tmp_path):
    store = ProductStore(str(tmp_path / "db.sqlite3"))
    pid = store.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    products = store.list_active()
    assert len(products) == 1
    assert products[0].id == pid
    assert products[0].button_label == "Amrr Activator Pro Tool A12+"


def test_product_store_inactive_excluded(tmp_path):
    store = ProductStore(str(tmp_path / "db.sqlite3"))
    pid = store.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)
    store.update(pid, "A12+", "Amrr Activator Pro Tool A12+", 50000, 0, 0)
    assert store.list_active() == []


def test_request_store_create_order_success(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 100000)
    pid = products.create_product("A12+", "Amrr Activator Pro Tool A12+", 50000)

    request_id = requests.create_order(uid, pid, "SN123", 50000)
    assert request_id is not None
    assert users.get_by_id(uid).balance == 50000
    record = requests.get_request(request_id)
    assert record.status == "pending"
    assert record.price_charged == 50000


def test_request_store_create_order_insufficient_balance(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    pid = products.create_product("A12+", "btn", 50000)

    result = requests.create_order(uid, pid, "SN123", 50000)
    assert result is None
    assert users.get_by_id(uid).balance == 0


def test_request_store_lifecycle(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 100000)
    pid = products.create_product("A12+", "btn", 50000)
    rid = requests.create_order(uid, pid, "SN123", 50000)

    requests.mark_success(rid, "Aktivasi berhasil")
    record = requests.get_request(rid)
    assert record.status == "success"
    assert record.reply_text == "Aktivasi berhasil"


def test_request_store_get_by_user(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    users = UserStore(db)
    products = ProductStore(db)
    requests = RequestStore(db)

    uid = users.create_user("alice", "hash")
    users._add_balance(uid, 200000)
    pid = products.create_product("A12+", "btn", 50000)
    requests.create_order(uid, pid, "SN1", 50000)
    requests.create_order(uid, pid, "SN2", 50000)

    rows = requests.get_by_user(uid)
    assert len(rows) == 2
    assert rows[0].product_name == "A12+"
