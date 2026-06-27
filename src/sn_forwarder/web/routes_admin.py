from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth import get_csrf_token, hash_password, require_admin

router = APIRouter()


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    require_admin(request, request.app.state.user_store)
    users = request.app.state.user_store.list_all()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        request, "admin/users.html", {"users": users, "csrf_token": csrf}
    )


@router.post("/users")
async def admin_create_user(request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", "")).strip()
    role = str(form.get("role", "user")).strip()
    if username and password:
        request.app.state.user_store.create_user(username, hash_password(password), role=role)
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/toggle")
async def admin_toggle_user(user_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    user = request.app.state.user_store.get_by_id(user_id)
    if user:
        request.app.state.user_store.set_active(user_id, 0 if user.is_active else 1)
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/topup")
async def admin_topup(user_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    amount = int(form.get("amount", 0))
    if amount > 0:
        request.app.state.balance_service.topup(user_id, amount, note="topup admin")
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/products", response_class=HTMLResponse)
async def admin_products(request: Request):
    require_admin(request, request.app.state.user_store)
    products = request.app.state.product_store.list_all()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        request, "admin/products.html", {"products": products, "csrf_token": csrf}
    )


@router.post("/products")
async def admin_create_product(request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    button_label = str(form.get("button_label", "")).strip()
    price = int(form.get("price", 0))
    sort_order = int(form.get("sort_order", 0))
    if name and button_label and price > 0:
        request.app.state.product_store.create_product(name, button_label, price, sort_order)
    return RedirectResponse(url="/admin/products", status_code=302)


@router.post("/products/{product_id}")
async def admin_update_product(product_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    button_label = str(form.get("button_label", "")).strip()
    price = int(form.get("price", 0))
    is_active = int(form.get("is_active", 1))
    sort_order = int(form.get("sort_order", 0))
    request.app.state.product_store.update(product_id, name, button_label, price, is_active, sort_order)
    return RedirectResponse(url="/admin/products", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def admin_history(request: Request):
    require_admin(request, request.app.state.user_store)
    rows = request.app.state.request_store.get_all(limit=100)
    return request.app.state.templates.TemplateResponse(
        request, "admin/history.html", {"rows": rows}
    )


@router.get("/apikeys", response_class=HTMLResponse)
async def admin_apikeys(request: Request):
    require_admin(request, request.app.state.user_store)
    keys = request.app.state.api_key_store.list_all()
    users = request.app.state.user_store.list_all()
    csrf = get_csrf_token(request)
    return request.app.state.templates.TemplateResponse(
        request, "admin/apikeys.html", {"keys": keys, "users": users, "csrf_token": csrf}
    )


@router.post("/apikeys")
async def admin_create_apikey(request: Request):
    require_admin(request, request.app.state.user_store)
    form = await request.form()
    user_id = int(form.get("user_id", 0))
    label = str(form.get("label", "")).strip()
    if user_id:
        request.app.state.api_key_store.create(user_id, label)
    return RedirectResponse(url="/admin/apikeys", status_code=302)


@router.post("/apikeys/{key_id}/revoke")
async def admin_revoke_apikey(key_id: int, request: Request):
    require_admin(request, request.app.state.user_store)
    request.app.state.api_key_store.revoke(key_id)
    return RedirectResponse(url="/admin/apikeys", status_code=302)
