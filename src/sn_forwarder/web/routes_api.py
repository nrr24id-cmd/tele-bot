from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..store import ApiKeyStore, ProductStore, RequestStore
from ..balance import BalanceService
from ..worker import RegistrationJob

router = APIRouter()

STATUS_MAP = {
    "pending": "Pending",
    "processing": "Processing",
    "success": "Completed",
    "failed": "Cancelled",
}


def _auth(request: Request, api_key: str) -> bool:
    store: ApiKeyStore = request.app.state.api_key_store
    record = store.get_by_key(api_key)
    return record is not None


@router.post("/wrapper/api/index.php")
async def dhru_api(request: Request):
    form = await request.form()
    api_key = str(form.get("key", ""))
    action = str(form.get("action", ""))

    if not _auth(request, api_key):
        return JSONResponse({"error": "Invalid API key"}, status_code=401)

    key_record = request.app.state.api_key_store.get_by_key(api_key)
    user_id = key_record.user_id

    if action == "balance":
        user = request.app.state.user_store.get_by_id(user_id)
        return JSONResponse({"balance": str(user.balance), "currency": "IDR"})

    elif action == "services":
        products = request.app.state.product_store.list_active()
        return JSONResponse([
            {
                "service": str(p.id),
                "name": p.name,
                "type": "sim",
                "rate": str(p.price),
                "min": "1",
                "max": "1",
                "dripfeed": "0",
                "refill": "0",
                "cancel": "0",
                "category": "SN Activation",
            }
            for p in products
        ])

    elif action == "order":
        service_id_raw = form.get("service", "")
        sn = str(form.get("serial", "")).strip()

        try:
            product_id = int(service_id_raw)
        except (ValueError, TypeError):
            return JSONResponse({"error": "Invalid service"}, status_code=400)

        product = request.app.state.product_store.get_by_id(product_id)
        if not product or not product.is_active:
            return JSONResponse({"error": "Service not found"}, status_code=404)

        if not sn:
            return JSONResponse({"error": "Serial number required"}, status_code=400)

        request_id = request.app.state.request_store.create_order(
            user_id, product.id, sn, product.price
        )
        if request_id is None:
            return JSONResponse({"error": "Insufficient balance"}, status_code=402)

        job = RegistrationJob(
            request_id=request_id,
            user_id=user_id,
            product_id=product.id,
            sn=sn,
            button_label=product.button_label,
            price_charged=product.price,
        )
        await request.app.state.worker.enqueue(job)
        return JSONResponse({"order": str(request_id)})

    elif action == "status":
        order_id_raw = form.get("orderid", "")
        try:
            order_id = int(order_id_raw)
        except (ValueError, TypeError):
            return JSONResponse({"error": "Invalid order ID"}, status_code=400)

        try:
            record = request.app.state.request_store.get_request(order_id)
        except (KeyError, Exception):
            return JSONResponse({"error": "Order not found"}, status_code=404)

        if record.user_id != user_id:
            return JSONResponse({"error": "Forbidden"}, status_code=403)

        return JSONResponse({
            "order": str(record.id),
            "status": STATUS_MAP.get(record.status, record.status),
            "charge": str(record.price_charged),
            "start_count": "0",
            "remains": "0",
            "currency": "IDR",
            "answer": record.reply_text or record.error_text or "",
        })

    else:
        return JSONResponse({"error": "Unknown action"}, status_code=400)
