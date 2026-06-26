# Task 6 Report — FastAPI App + Session Auth

## Status
COMPLETE — 4/4 tests passed, full suite 27/27 passed.

## Files Created
- `src/sn_forwarder/web/__init__.py` — empty package init
- `src/sn_forwarder/web/auth.py` — bcrypt password hashing, session helpers, CSRF, brute-force lockout, `require_user`/`require_admin`, `NotAuthenticatedException`
- `src/sn_forwarder/web/app.py` — `build_web_app()` factory: SessionMiddleware, login/logout routes, exception handler for `NotAuthenticatedException` → 302 to `/login`
- `src/sn_forwarder/web/routes_panel.py` — stub with `/dashboard` route (calls `require_user`)
- `src/sn_forwarder/web/routes_admin.py` — stub with `/admin/users` route (calls `require_admin`)
- `src/sn_forwarder/web/templates/login.html`
- `src/sn_forwarder/web/templates/base.html`
- `src/sn_forwarder/web/templates/dashboard.html`
- `tests/test_web_auth.py`
- `requirements.txt` — added `bcrypt==4.0.1` pin

## Test Results
```
4 passed (test_web_auth.py)
27 passed total (full suite)
```

## Deviations from Spec

### 1. `require_user` raises `NotAuthenticatedException` instead of `RedirectResponse`
The spec said to `raise RedirectResponse(...)` and add an `@app.exception_handler(RedirectResponse)` handler. This does not work: Starlette's `ExceptionMiddleware.add_exception_handler` asserts `issubclass(exc_class, Exception)`, and `RedirectResponse` is not an `Exception` subclass — registering it raises `AssertionError` at app startup.

Fix: introduced `NotAuthenticatedException(Exception)` in `auth.py`. `require_user` raises this, and `app.py` registers `@app.exception_handler(NotAuthenticatedException)` which returns a `RedirectResponse(url="/login", status_code=302)`. Behavior is identical.

### 2. `bcrypt==4.0.1` pinned in requirements.txt
The venv had `bcrypt==5.0.0` installed. bcrypt 5.x raises `ValueError` when hashing passwords >72 bytes; passlib 1.7.4's backend detection probe uses a 255-byte password internally, triggering this error before any user-facing `hash()` call. Downgraded to `bcrypt==4.0.1` (last version passlib 1.7.4 is tested against) and pinned it in `requirements.txt`.

### 3. Template deprecation warning
Starlette recommends `TemplateResponse(request, name)` signature (request first) rather than `TemplateResponse(name, {"request": request})`. This produces one `DeprecationWarning` per affected response. Not a test failure; will be fixed when templates are fleshed out in Tasks 7–8.

## Commit Hash
(see git log after commit)
