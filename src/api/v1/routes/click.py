from fastapi import APIRouter, Request

from src.billing.order_service import OrderService
from src.core.conf import CLICK_SECRET_KEY
from src.utils.helper import click_generate_sign_string

router = APIRouter(prefix="/click", tags=["click"])

def verify_signature(payload: dict) -> bool:
    """Recalculate Click signature and compare"""
    calc_sign = click_generate_sign_string(
        payload["click_trans_id"],
        payload["service_id"],
        CLICK_SECRET_KEY,
        payload["merchant_trans_id"],
        payload.get("merchant_prepare_id", ""),
        payload["amount"],
        payload["action"],
        payload["sign_time"],
    )
    return calc_sign == payload["sign_string"]

@router.post("/prepare")
async def click_prepare(request: Request):
    payload = dict(await request.form())

    # 1️⃣ Verify signature
    if not verify_signature(payload):
        return {"error": -1, "error_note": "SIGN CHECK FAILED"}

    # 2️⃣ Validate order exists
    order_id = payload["merchant_trans_id"]
    order_data = await OrderService.get_order(order_id)
    if not order_data and order_data.status != "pending":
        return {"error": -5, "error_note": "Order not found"}


    if float(payload["amount"]) != float(order_data["amount"]):
        return {"error": -2, "error_note": "Incorrect amount"}

    # 3️⃣ Return OK (merchant_prepare_id is usually your internal ID)
    return {
        "click_trans_id": payload["click_trans_id"],
        "merchant_trans_id": order_id,
        "merchant_prepare_id": order_data.id,
        "error": 0,
        "error_note": "Success",
    }

@router.post("/complete")
async def click_complete(request: Request):
    payload = dict(await request.form())

    # 1️⃣ Verify signature
    if not verify_signature(payload):
        return {"error": -1, "error_note": "SIGN CHECK FAILED"}

    order_id = payload["merchant_trans_id"]
    order_data = await OrderService.get_order(order_id)
    if not order_data and order_data.status != "pending":
        return {"error": -5, "error_note": "Order not found"}

    if float(payload["amount"]) != float(order_data["amount"]):
        return {"error": -2, "error_note": "Incorrect amount"}

    # 2️⃣ Update order status
    await OrderService.mark_order_paid(
        order_id=order_id,
        transaction_id=payload["click_trans_id"],
        payment_provider='click',
        amount=order_data["amount"],

    )

    # 3️⃣ Respond success
    return {
        "click_trans_id": payload["click_trans_id"],
        "merchant_trans_id": order_id,
        "merchant_confirm_id": order_data.id,
        "error": 0,
        "error_note": "Success",
    }