from datetime import datetime, timedelta
import uuid
import json
from typing import Optional, List
from fastapi import HTTPException, status

from src.core.db import DatabaseConnection
from src.core.conf import PRICING, ORDER_EXPIRATION_HOURS
from src.models.billing import OrderCreate, Order


class OrderService:
    @staticmethod
    def calculate_order_amount(plan: str, months: int) -> float:
        """Calculate total order amount"""
        price_per_month = PRICING.get(plan, 0)

        # Apply discounts for longer subscriptions
        discount = 0
        if months >= 12:
            discount = 0.20  # 20% discount for 12+ months
        elif months >= 6:
            discount = 0.10  # 10% discount for 6-11 months
        elif months >= 3:
            discount = 0.05  # 5% discount for 3-5 months

        total = price_per_month * months
        discounted_total = total * (1 - discount)

        return round(discounted_total, 2)

    @staticmethod
    async def create_order(user_id: str, subscription_plan: str, order_data: OrderCreate) -> Order:
        """Create a new order"""
        # Check is it user downgrades the plan
        order_plan = order_data.plan
        if subscription_plan != "free-trial" and order_plan != subscription_plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Changing plan is unavailable at the moment. Please wait until your subscription period ends, then renew your plan."
            )


        order_id = str(uuid.uuid4())
        amount = OrderService.calculate_order_amount(order_plan, order_data.months)
        expires_at = datetime.utcnow() + timedelta(hours=ORDER_EXPIRATION_HOURS)

        async with DatabaseConnection() as db:
            await db.execute_one(
                query="UPDATE orders SET status = 'cancelled' WHERE user_id = ? AND status = 'pending'",
                params=(user_id, ),
                commit=False
            )
            await db.execute_one(
                query="""
                    INSERT INTO orders (
                        id, user_id, plan, months, amount, currency, 
                        status, payment_provider, created_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'UZS', 'pending', ?, ?, ?)
                """,
                params=(
                    order_id, user_id, order_data.plan, order_data.months,
                    amount, order_data.payment_provider, datetime.utcnow(), expires_at
                ),
                commit=True
            )

            # Fetch the created order
            row = await db.fetch_one(
                query="SELECT * FROM orders WHERE id = ?",
                params=(order_id,)
            )

        return OrderService._row_to_order(row)

    @staticmethod
    async def get_order(order_id: str) -> Optional[Order]:
        """Get order by ID"""
        async with DatabaseConnection() as db:
            row = await db.fetch_one(
                query="SELECT * FROM orders WHERE id = ?",
                params=(order_id,),
                allow_none=True
            )

        if not row:
            return None

        return OrderService._row_to_order(row)

    @staticmethod
    async def get_user_orders(user_id: str, status: Optional[str] = None) -> List[Order]:
        """Get all orders for a user, optionally filtered by status"""
        async with DatabaseConnection() as db:
            if status:
                rows = await db.fetch_all(
                    query="SELECT * FROM orders WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                    params=(user_id, status)
                )
            else:
                rows = await db.fetch_all(
                    query="SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
                    params=(user_id,)
                )

        return [OrderService._row_to_order(row) for row in rows]

    @staticmethod
    async def mark_order_paid(
            order_id: str,
            transaction_id: str,
            payment_provider: str,
            amount: Optional[float] = None,
            metadata: Optional[dict] = None
    ) -> Order:
        """Mark an order as paid"""
        order = await OrderService.get_order(order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        if order.status == 'paid':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already paid"
            )

        if order.status in ['cancelled', 'expired']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot mark {order.status} order as paid"
            )

        # Verify amount if provided
        if amount and abs(amount - order.amount) > 0.01:  # Allow 1 cent difference
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount mismatch. Expected: {order.amount}, Received: {amount}"
            )

        metadata_str = json.dumps(metadata) if metadata else None

        async with DatabaseConnection() as db:
            await db.execute_one(
                query="""
                    UPDATE orders 
                    SET status = 'paid', 
                        paid_at = ?,
                        payment_transaction_id = ?,
                        payment_provider = ?,
                        metadata = ?
                    WHERE id = ?
                """,
                params=(datetime.utcnow(), transaction_id, payment_provider, metadata_str, order_id)
            )

            row = await db.fetch_one(
                query="SELECT * FROM orders WHERE id = ?",
                params=(order_id,)
            )

        return OrderService._row_to_order(row)

    @staticmethod
    async def mark_order_failed(
            order_id: str,
            transaction_id: Optional[str] = None,
            metadata: Optional[dict] = None
    ) -> Order:
        """Mark an order as failed"""
        order = await OrderService.get_order(order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        if order.status == 'paid':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark paid order as failed"
            )

        metadata_str = json.dumps(metadata) if metadata else None

        async with DatabaseConnection() as db:
            await db.execute_one(
                query="""
                    UPDATE orders 
                    SET status = 'failed',
                        payment_transaction_id = ?,
                        metadata = ?
                    WHERE id = ?
                """,
                params=(transaction_id, metadata_str, order_id)
            )

            row = await db.fetch_one(
                query="SELECT * FROM orders WHERE id = ?",
                params=(order_id,)
            )

        return OrderService._row_to_order(row)

    @staticmethod
    async def cancel_order(order_id: str) -> Order:
        """Cancel an order"""
        order = await OrderService.get_order(order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        if order.status == 'paid':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel paid order"
            )

        if order.status in ['cancelled', 'expired']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order is already {order.status}"
            )

        async with DatabaseConnection() as db:
            await db.execute_one(
                query="UPDATE orders SET status = 'cancelled' WHERE id = ?",
                params=(order_id,)
            )

            row = await db.fetch_one(
                query="SELECT * FROM orders WHERE id = ?",
                params=(order_id,)
            )

        return OrderService._row_to_order(row)

    @staticmethod
    async def expire_old_orders():
        """Expire orders that haven't been paid within the expiration time"""
        async with DatabaseConnection() as db:
            result = await db.execute_one(
                query="""
                    UPDATE orders 
                    SET status = 'expired' 
                    WHERE status = 'pending' 
                    AND expires_at < ?
                """,
                params=(datetime.utcnow(),)
            )

        return result.get("rows_affected", 0)

    @staticmethod
    def _row_to_order(row) -> Order:
        """Convert core row to Order model"""
        return Order(
            id=row[0],
            user_id=row[1],
            plan=row[2],
            months=row[3],
            amount=row[4],
            currency=row[5],
            status=row[6],
            payment_provider=row[7],
            payment_transaction_id=row[8],
            created_at=row[9],
            paid_at=row[10],
            expires_at=row[11],
            metadata=row[12]
        )