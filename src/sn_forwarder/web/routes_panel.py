from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..worker import RegistrationJob
from .auth import get_csrf_token, require_user, verify_csrf

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = require_user(request, request.app.state.user_store)
    fresh = request.app.state.user_store.get_by_id(user.id)
    return request.app.state.templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": fresh}
    )


@router.get("/order", response_class=HTMLResponse)
async def order_page(request: Request):
    user = require_user(request, request.app.state.user_store)
    products = request.app.state.product_store.list_active()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        "order.html",
        {"request": request, "user": user, "products": products, "csrf_token": csrf, "error": None},
    )


@router.post("/order")
async def order_post(request: Request):
    user = require_user(request, request.app.state.user_store)
    form = await request.form()
    csrf = str(form.get("csrf_token", ""))
    if not verify_csrf(request, csrf):
        return RedirectResponse(url="/login", status_code=302)

    product_id_raw = form.get("product_id", "")
    sn = str(form.get("sn", "")).strip()

    try:
        product_id = int(product_id_raw)
    except (ValueError, TypeError):
        return _order_error(request, user, "Produk tidak valid.")

    product = request.app.state.product_store.get_by_id(product_id)
    if not product or not product.is_active:
        return _order_error(request, user, "Produk tidak valid.")

    if not sn:
        return _order_error(request, user, "SN tidak boleh kosong.")

    request_id = request.app.state.request_store.create_order(
        user.id, product.id, sn, product.price
    )
    if request_id is None:
        return _order_error(request, user, "Saldo tidak cukup. Hubungi admin untuk top-up.")

    job = RegistrationJob(
        request_id=request_id,
        user_id=user.id,
        product_id=product.id,
        sn=sn,
        button_label=product.button_label,
        price_charged=product.price,
    )
    await request.app.state.worker.enqueue(job)
    return RedirectResponse(url=f"/history?submitted={request_id}", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    user = require_user(request, request.app.state.user_store)
    rows = request.app.state.request_store.get_by_user(user.id, limit=50)
    submitted = request.query_params.get("submitted")
    return request.app.state.templates.TemplateResponse(
        "history.html", {"request": request, "user": user, "rows": rows, "submitted": submitted}
    )


@router.get("/transactions", response_class=HTMLResponse)
async def transactions(request: Request):
    user = require_user(request, request.app.state.user_store)
    fresh = request.app.state.user_store.get_by_id(user.id)
    txns = request.app.state.balance_service.get_transactions(user.id)
    return request.app.state.templates.TemplateResponse(
        "transactions.html", {"request": request, "user": fresh, "txns": txns}
    )


@router.get("/api/request/{request_id}/status")
async def request_status(request_id: int, request: Request):
    user = require_user(request, request.app.state.user_store)
    try:
        record = request.app.state.request_store.get_request(request_id)
    except KeyError:
        return JSONResponse({"error": "not found"}, status_code=404)
    if record.user_id != user.id and user.role != "admin":
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse({"status": record.status, "reply_text": record.reply_text, "error_text": record.error_text})


def _order_error(request: Request, user, message: str):
    products = request.app.state.product_store.list_active()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        "order.html",
        {"request": request, "user": user, "products": products, "csrf_token": csrf, "error": message},
        status_code=200,
    )
