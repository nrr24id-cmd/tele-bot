from __future__ import annotations

import defusedxml.ElementTree as ET

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
    for r in store.list_all():
        if r.api_key == api_key and r.is_active:
            user = request.app.state.user_store.get_by_id(r.user_id)
            if user and user.username == username:
                return user
    return None


def _err(msg: str, status: int = 400):
    return JSONResponse({"ERROR": [{"MESSAGE": msg}]}, status_code=status)


def _parse_xml_params(raw: str) -> dict:
    """Parse XML parameters field sent by DHRU panels."""
    result = {}
    try:
        root = ET.fromstring(raw)
        for child in root:
            result[child.tag] = (child.text or "").strip()
    except Exception:
        pass
    return result


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
        return JSONResponse({
            "SUCCESS": "1",
            "MESSAGE": "OK",
            "BALANCE": str(user.balance),
            "CURRENCY": "IDR",
            "mail": user.username,
        })

    elif action == "imeiservicelist":
        products = request.app.state.product_store.list_active()
        services = {}
        for p in products:
            sid = f"svc_{p.id}"
            services[sid] = {
                "SERVICEID": sid,
                "SERVICENAME": p.name,
                "CREDIT": str(p.price),
            }
        list_data = {
            "SN": {
                "GROUPNAME": "SN SERVICES",
                "GROUPTYPE": "SN",
                "SERVICES": services,
            }
        }
        return JSONResponse({"SUCCESS": [{"MESSAGE": "Service List", "LIST": list_data}]})

    elif action == "placeimeiorder":
        # Parse XML parameters jika ada (format DHRU panel)
        xml_params = {}
        raw_params = str(form.get("parameters", "")).strip()
        if raw_params:
            xml_params = _parse_xml_params(raw_params)

        # Service ID bisa di field ID atau SERVICEID, atau dari XML
        service_id_raw = (
            xml_params.get("ID") or xml_params.get("SERVICEID")
            or str(form.get("ID", "") or form.get("SERVICEID", "")).strip()
        )
        if not service_id_raw:
            return _err("SERVICEID required", 400)

        # Input value: cari di XML dulu, lalu flat POST
        input_val = ""
        for field in ["SN", "IMEI", "ECID", "EMAIL", "USERNAME"]:
            v = xml_params.get(field) or str(form.get(field, "")).strip()
            if v:
                input_val = v
                break

        if not service_id_raw.startswith("svc_"):
            return _err("Service not found or inactive", 404)

        try:
            product_id = int(service_id_raw[4:])
        except (ValueError, TypeError):
            return _err("Service not found or inactive", 404)

        product = request.app.state.product_store.get_by_id(product_id)
        if not product or not product.is_active:
            return _err("Service not found or inactive", 404)

        if not input_val:
            return _err("IMEI/SN required", 400)

        request_id = request.app.state.request_store.create_order(
            user.id, product.id, input_val, product.price
        )
        if request_id is None:
            return _err("Insufficient balance", 402)

        job = RegistrationJob(
            request_id=request_id,
            user_id=user.id,
            product_id=product.id,
            sn=input_val,
            button_label=product.button_label,
            price_charged=product.price,
        )
        await request.app.state.worker.enqueue(job)
        return JSONResponse({"SUCCESS": [{"MESSAGE": "Order Accepted", "OrderID": str(request_id), "REFERENCEID": str(request_id)}]})

    elif action == "getimeiorder":
        # ID bisa dari XML parameters atau flat POST
        xml_params = {}
        raw_params = str(form.get("parameters", "")).strip()
        if raw_params:
            xml_params = _parse_xml_params(raw_params)

        order_id_raw = xml_params.get("ID") or str(form.get("ID", "")).strip()
        if not order_id_raw:
            return _err("Parameter 'ID' required", 400)

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
        }]})

    else:
        return _err("Unknown action", 400)
