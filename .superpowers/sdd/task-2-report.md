# Task 2 Report: Schema — UserStore, ProductStore, RequestStore

## Status
COMPLETE

## Commit
`ffea848` — feat: expand store with users, products, requests revision, transactions

## Test Summary (test_store.py)
9/9 passed

```
tests/test_store.py::test_user_store_create_and_get          PASSED
tests/test_store.py::test_user_store_duplicate_username_raises PASSED
tests/test_store.py::test_user_store_set_active              PASSED
tests/test_store.py::test_product_store_create_and_list      PASSED
tests/test_store.py::test_product_store_inactive_excluded    PASSED
tests/test_store.py::test_request_store_create_order_success PASSED
tests/test_store.py::test_request_store_create_order_insufficient_balance PASSED
tests/test_store.py::test_request_store_lifecycle            PASSED
tests/test_store.py::test_request_store_get_by_user          PASSED
```

## Full Suite
- 13 passed, 2 failed
- Failures are in `tests/test_worker.py` — expected, worker.py still uses old `create_request` API (fixed in Task 5)
- test_config.py: all pass

## Changes Made
- `src/sn_forwarder/store.py`: Full rewrite — 4 tables (users, products, requests, transactions), WAL mode, `isolation_level=None`, manual BEGIN/COMMIT/ROLLBACK, `BEGIN IMMEDIATE` atomic order creation
- `tests/test_store.py`: Full rewrite with 9 tests covering all store classes

## Fix Applied During Implementation
`ProductRecord` dataclass was missing the `created_at` field that exists in the DB schema (caused one initial test failure). Added the field to match the DB row shape.

## Concerns
- `test_worker.py` failures are pre-existing (old API, Task 5 will fix)
- `asyncio_default_fixture_loop_scope` deprecation warning from pytest-asyncio is cosmetic — not a test failure
