from fastapi import APIRouter, Request, HTTPException
import logging

from src.billing.order_service import OrderService
from src.billing.payment_service import PaymentService
from src.billing.subscription_service import SubscriptionService
from src.core.conf import CLICK_SECRET_KEY
from src.models.billing import PaymentCreateRequest
from src.utils.helper import click_generate_sign_string

logger = logging.getLogger("DocVision")

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
        logger.info("SIGN CHECK FAILED")
        return {"error": -1, "error_note": "SIGN CHECK FAILED"}

    # 2️⃣ Validate order exists
    order_id = payload["merchant_trans_id"]
    order_data = await OrderService.get_order(order_id)
    if not order_data and order_data.status != "pending":
        logger.info("Order not found")
        return {"error": -5, "error_note": "Order not found"}


    if float(payload["amount"]) != float(order_data.amount):
        return {"error": -2, "error_note": "Incorrect amount"}

    if order_data.status == "paid":
        return {"error": -2, "error_note": "Order is already paid"}

    # 3️⃣ Return OK (merchant_prepare_id is usually your internal ID)
    logger.info("Click payment prepared successfully")
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
        logger.info("SIGN CHECK FAILED")
        return {"error": -1, "error_note": "SIGN CHECK FAILED"}

    order_id = payload["merchant_trans_id"]
    order_data = await OrderService.get_order(order_id)
    if not order_data and order_data.status != "pending":
        return {"error": -5, "error_note": "Order not found"}

    if float(payload["amount"]) != float(order_data.amount):
        logger.info("Incorrect amount")
        return {"error": -2, "error_note": "Incorrect amount"}

    user_id = order_data.user_id
    # Add payment to the db
    payment_result = await PaymentService.create_payment(
        PaymentCreateRequest(
            amount=order_data.amount,
            provider='click',
            user_id=user_id
        )
    )

    if not payment_result:
        logger.error("Payment creation failed")
        raise HTTPException(status_code=500, detail="Payment creation failed")

    # 2️⃣ Update order status
    await OrderService.mark_order_paid(
        order_id=order_id,
        transaction_id=payload["click_trans_id"],
        payment_provider='click',
        amount=order_data.amount
    )
    logger.info("Order is marked as paid")

    # Activate subscription
    await SubscriptionService.activate_subscription(
        user_id=user_id,
        plan=order_data.plan,
        months=order_data.months
    )

    # 3️⃣ Respond success
    logger.info("Click payment completed successfully")
    return {
        "click_trans_id": payload["click_trans_id"],
        "merchant_trans_id": order_id,
        "merchant_confirm_id": order_data.id,
        "error": 0,
        "error_note": "Success",
    }