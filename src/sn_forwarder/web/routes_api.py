from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..store import ApiKeyStore
from ..worker import RegistrationJob

router = APIRouter()

STATUS_MAP = {
    "pending": "0",
    "processing": "1",
    "failed": "3",
    "success": "4",
}


def _auth(request: Request, username: str, api_key: str):
    store: ApiKeyStore = request.app.state.api_key_store
    if not store:
        return None
    records = store.list_all()
    for r in records:
        if r.api_key == api_key and r.is_active:
            user = request.app.state.user_store.get_by_id(r.user_id)
            if user and user.username == username:
                return user
    return None


def _err(msg: str, status: int = 400):
    return JSONResponse({"ERROR": [{"MESSAGE": msg}]}, status_code=status)


@router.post("/api")
async def imore_api(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    api_key = str(form.get("apiaccesskey", "")).strip()
    action = str(form.get("action", "")).strip()

    if not username or not api_key:
        return _err("Credentials required", 401)

    user = _auth(request, username, api_key)
    if user is None:
        return _err("Invalid credentials", 401)

    if action == "accountinfo":
        return JSONResponse({"SUCCESS": [{
            "MESSAGE": "OK",
            "BALANCE": str(user.balance),
            "CURRENCY": "IDR",
            "mail": user.username,
        }]})

    elif action == "imeiservicelist":
        products = request.app.state.product_store.list_active()
        services = [{
            "SERVICEID": f"svc_{p.id}",
            "SERVICENAME": p.name,
            "CREDIT": str(p.price),
            "TYPE": "SN",
        } for p in products]
        return JSONResponse({"SUCCESS": [{"MESSAGE": "Service List", "SERVICES": services}]})

    elif action == "placeimeiorder":
        service_id_raw = str(form.get("SERVICEID", "")).strip()
        sn = str(form.get("SN", "") or form.get("IMEI", "")).strip()

        if not service_id_raw.startswith("svc_"):
            return _err("Service not found or inactive", 404)

        try:
            product_id = int(service_id_raw[4:])
        except (ValueError, TypeError):
            return _err("Service not found or inactive", 404)

        product = request.app.state.product_store.get_by_id(product_id)
        if not product or not product.is_active:
            return _err("Service not found or inactive", 404)

        if not sn:
            return _err("IMEI/SN required", 400)

        request_id = request.app.state.request_store.create_order(
            user.id, product.id, sn, product.price
        )
        if request_id is None:
            return _err("Insufficient balance", 402)

        job = RegistrationJob(
            request_id=request_id,
            user_id=user.id,
            product_id=product.id,
            sn=sn,
            button_label=product.button_label,
            price_charged=product.price,
        )
        await request.app.state.worker.enqueue(job)
        return JSONResponse({"SUCCESS": [{"MESSAGE": "Order placed", "ID": f"ord_{request_id}"}]})

    elif action == "getimeiorder":
        order_id_raw = str(form.get("ID", "")).strip()
        if order_id_raw.startswith("ord_"):
            order_id_raw = order_id_raw[4:]
        try:
            order_id = int(order_id_raw)
        except (ValueError, TypeError):
            return _err("Order not found", 404)

        try:
            record = request.app.state.request_store.get_request(order_id)
        except Exception:
            return _err("Order not found", 404)

        if record.user_id != user.id:
            return _err("Order not found", 404)

        return JSONResponse({"SUCCESS": [{
            "STATUS": STATUS_MAP.get(record.status, "0"),
            "CODE": record.reply_text or record.error_text or "",
            "ID": f"ord_{record.id}",
        }]})

    else:
        return _err("Unknown action", 400)
