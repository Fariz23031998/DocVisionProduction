from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status

from src.billing.order_service import OrderService
from src.billing.payment_service import PaymentService
from src.billing.subscription_service import SubscriptionService
from src.core.conf import ORDER_EXPIRATION_HOURS, PLANS_CONFIG, format_click_url, ADMIN_CODE
from src.core.security import get_current_user
from src.models.billing import OrderResponse, OrderCreate, Order, SubscriptionActivate, \
    SubscriptionSummary, SubscriptionActivateForce
from src.models.user import User
from src.core.db import DatabaseConnection

router = APIRouter(prefix="/billing", tags=["Billings"])

@router.get("/subscription", response_model=SubscriptionSummary)
async def get_user_subscription(current_user: User = Depends(get_current_user)):
    """Get current user's subscription details"""
    plan_info = await SubscriptionService.get_plan_info(current_user.id)
    return plan_info


# Activate or extend subscription
@router.post("/subscription/activate")
async def activate_subscription(
        data: SubscriptionActivateForce
):
    """
    Activate or extend user's subscription
    - Upgrades from free-trial to paid plan
    - Extends existing subscription by adding months
    - Upgrades between paid plans
    """
    if data.code != ADMIN_CODE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation code"
        )

    async with DatabaseConnection() as db:
        user_info = await db.fetch_one(
                query="SELECT id FROM users WHERE email = ?", 
                params=(data.email,),
                raise_http=True
            )

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user_id = user_info[0]
    await SubscriptionService.activate_subscription(
        user_id=user_id,
        plan=data.plan,
        months=data.months
    )

    return {"ok": True, "message": "Subscription activated"}


# Create order
@router.post("/orders", response_model=OrderResponse)
async def create_order(
        order_data: OrderCreate,
        current_user: User = Depends(get_current_user)
):
    """Create a new subscription order"""
    user_id = current_user.id
    subscription_info = await SubscriptionService.get_subscription(user_id)
    subscription_plan = subscription_info.plan if subscription_info else "None"
    if order_data.payment_provider == "click":
        order = await OrderService.create_order(user_id, subscription_plan, order_data)

        payment_url = format_click_url(transaction_param=order.id, amount=order.amount)

        return OrderResponse(
            order=order,
            message=f"Order created successfully. Please complete payment within {ORDER_EXPIRATION_HOURS} hours.",
            payment_url=payment_url
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment provider not supported"
        )


# Get user's orders
@router.get("/orders")
async def get_orders(
        order_status: Optional[str] = None,
        current_user: User = Depends(get_current_user)
):
    """Get all orders for current user, optionally filtered by status"""
    orders = await OrderService.get_user_orders(current_user.id, order_status)
    return {"orders": orders}


# Get specific order
@router.get("/orders/{order_id}", response_model=Order)
async def get_order(
        order_id: str,
        current_user: User = Depends(get_current_user)
):
    """Get specific order details"""
    order = await OrderService.get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Verify order belongs to user
    if order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return order

# Cancel order
@router.post("/orders/{order_id}/cancel")
async def cancel_order(
        order_id: str,
        current_user: User = Depends(get_current_user)
):
    """Cancel a pending order"""
    order = await OrderService.get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Verify order belongs to user
    if order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    order = await OrderService.cancel_order(order_id)

    return {
        "message": "Order cancelled successfully",
        "order": order
    }

# Get pricing information
@router.get("/pricing")
async def get_pricing():
    """Get subscription pricing with discounts"""
    return PLANS_CONFIG

@router.get("/payments")
async def get_payments(current_user: User = Depends(get_current_user)):
    return await PaymentService.get_payments(current_user.id)

