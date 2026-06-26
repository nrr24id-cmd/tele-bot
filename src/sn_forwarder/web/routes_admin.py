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
        "admin/users.html", {"request": request, "users": users, "csrf_token": csrf}
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
        "admin/products.html", {"request": request, "products": products, "csrf_token": csrf}
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
        "admin/history.html", {"request": request, "rows": rows}
    )
