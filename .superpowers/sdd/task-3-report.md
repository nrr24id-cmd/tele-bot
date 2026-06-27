# Task 3: BalanceService Implementation — Report

## Status
**COMPLETED** ✓

## Summary
Successfully implemented `BalanceService` with balance management (topup, refund) and transaction ledger functionality. All tests passing.

## Files Created

### `src/sn_forwarder/balance.py`
- **BalanceService** class with methods:
  - `__init__(database_path)`: Initializes with database and calls `_init_all_tables()`
  - `topup(user_id, amount, note="")`: Atomically increases balance and records topup transaction
  - `refund(user_id, amount, ref_request_id)`: Atomically increases balance and records refund transaction linked to request
  - `get_transactions(user_id, limit=50)`: Retrieves recent transactions ordered DESC by created_at
- **TransactionRecord** dataclass with fields: id, user_id, type, amount, balance_after, ref_request_id, note, created_at
- All database operations use manual `BEGIN`/`COMMIT`/`ROLLBACK` with `isolation_level=None`
- Money handled as integer rupiah (no floats)
- Uses `sqlite3.Row` factory for dict conversion

### `tests/test_balance.py`
- **test_topup_increases_balance**: Verifies topup atomically increases user balance
- **test_topup_records_transaction**: Verifies topup transaction created with correct fields (type, amount, balance_after, note)
- **test_refund_increases_balance**: Verifies refund atomically increases balance (requires pre-existing request)
- **test_refund_records_transaction**: Verifies refund transaction records type='refund' and ref_request_id

## Test Results
```
tests/test_balance.py::test_topup_increases_balance PASSED               [ 25%]
tests/test_balance.py::test_topup_records_transaction PASSED             [ 50%]
tests/test_balance.py::test_refund_increases_balance PASSED              [ 75%]
tests/test_balance.py::test_refund_records_transaction PASSED            [100%]

============================== 4 passed in 0.17s ==============================
```

## Commit
- **Hash**: `0c79f196098f84ef312b2b4598350a7955153af4`
- **Branch**: `codex/telegram-sn-forwarder`
- **Message**: `feat: add balance service (topup, refund, ledger)`

## Implementation Details

### Architecture
- BalanceService follows the pattern of UserStore/ProductStore/RequestStore
- Uses `_make_connection()` with `isolation_level=None` for manual transaction control
- Each operation (topup/refund) is a complete atomic transaction

### Key Constraints Respected
- All money as integer rupiah (no floats)
- `isolation_level=None` connections with manual transaction control
- Foreign key constraint on `transactions.ref_request_id` REFERENCES `requests(id)`
- TransactionRecord uses frozen dataclass for immutability

### Test Coverage Notes
- Refund tests require pre-existing request (created via RequestStore.create_order)
  - Tests use tmp_path for isolated databases
  - Proper ordering to create request before attempting refund
  - Transaction lookup filters by type to handle debit + refund sequences

## No Known Issues
- All constraints properly enforced
- Transaction isolation working correctly
- Balance updates consistent with transaction records
