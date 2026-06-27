# Task 7 & 8 Report — User Panel + Admin Routes

## Status
Both tasks completed and committed.

## Commit Hashes
- Task 7: `deafb6b` — feat: add user panel routes (dashboard, order, history, transactions)
- Task 8: `ac7afec` — feat: add admin routes (users, products, topup, history)

## Test Results

### test_web_panel.py (Task 7) — 5 passed
- test_dashboard_shows_balance
- test_order_post_success
- test_order_post_insufficient_balance
- test_history_page
- test_status_api

### test_web_admin.py (Task 8) — 4 passed
- test_admin_can_create_product
- test_admin_topup_increases_balance
- test_admin_toggle_user
- test_non_admin_cannot_access_admin

### Full Suite — 36 passed, 0 failed

## Files Written

### Task 7
- `src/sn_forwarder/web/routes_panel.py` — replaced (dashboard, order GET/POST, history, transactions, /api/request/{id}/status)
- `src/sn_forwarder/web/templates/order.html`
- `src/sn_forwarder/web/templates/history.html` (includes JS polling for pending/processing status)
- `src/sn_forwarder/web/templates/transactions.html`
- `tests/test_web_panel.py`

### Task 8
- `src/sn_forwarder/web/routes_admin.py` — replaced (users CRUD, toggle, topup; products CRUD; history)
- `src/sn_forwarder/web/templates/admin/users.html`
- `src/sn_forwarder/web/templates/admin/products.html`
- `src/sn_forwarder/web/templates/admin/history.html`
- `tests/test_web_admin.py`

## Concerns / Notes
- Starlette `DeprecationWarning`: `TemplateResponse(name, {"request": request})` — the positional arg order is deprecated in newer Starlette. All existing callers (including Task 6's app.py) use the old form. This is cosmetic (6 warnings, all pass) and can be fixed wholesale in Task 9 or a cleanup pass by switching to `TemplateResponse(request, name)`.
- CSRF on admin POST routes: the spec does not require CSRF verification on admin POSTs (only `require_admin` guard). The tests do not send a csrf_token for admin actions and they pass. If stricter CSRF is desired on admin routes, it can be added uniformly in Task 9.
- `worker=None` is passed in admin tests (no order submission path needs it). The panel routes call `worker.enqueue()` only after a successful order, so `None` is safe for admin-only tests.
