from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid
from typing import Optional
from fastapi import HTTPException, status
import logging

from src.billing.order_service import OrderService
from src.core.conf import PLANS_CONFIG, PRICING
from src.core.db import DatabaseConnection
from src.models.billing import Subscription, SubscriptionUpdate

logger = logging.getLogger("DocVision")


class SubscriptionService:
    @staticmethod
    async def create_subscription(user_id: str, plan: str = 'free-trial', months: Optional[int] = None) -> Subscription:
        """Create a new subscription for a user"""
        subscription_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Calculate expiration date
        expires_at = None
        if plan == 'free-trial':
            # Free trial is always 7 days
            expires_at = now + timedelta(days=7)
        elif months:
            # Calculate expiration based on months
            expires_at = now + relativedelta(months=months)


        monthly_regeneration = PLANS_CONFIG.get(plan, {}).get("monthly_regeneration", 0)
        # In create_subscription method
        async with DatabaseConnection() as db:
            await db.execute_one(
                query="INSERT INTO ai_processing_operations (subscription_id, is_positive, amount) VALUES (?, ?, ?)",
                params=(subscription_id, True, monthly_regeneration)
            )

            await db.execute_one(
                query="""
                    INSERT INTO subscriptions (id, user_id, plan, status, ai_processing, last_monthly_regen, started_at, expires_at)
                    VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                params=(subscription_id, user_id, plan, monthly_regeneration, now, now, expires_at)
            )

            # Fetch the created subscription
            row = await db.fetch_one(
                query="SELECT * FROM subscriptions WHERE id = ?",
                params=(subscription_id,)
            )

        return Subscription(
            id=row[0],
            user_id=row[1],
            plan=row[2],
            status=row[3],
            ai_processing=row[4],
            last_monthly_regen=row[5],
            last_daily_regen=row[6],
            started_at=row[7],
            expires_at=row[8],
            cancelled_at=row[9]
        )

    @staticmethod
    async def get_subscription(user_id: str) -> Optional[Subscription]:
        """Get user's subscription"""
        async with DatabaseConnection() as db:
            row = await db.fetch_one(
                query="SELECT * FROM subscriptions WHERE user_id = ?",
                params=(user_id,),
                allow_none=True
            )

        if not row:
            return None

        return Subscription(
            id=row[0],
            user_id=row[1],
            plan=row[2],
            status=row[3],
            ai_processing=row[4],
            last_monthly_regen=row[5],
            last_daily_regen=row[6],
            started_at=row[7],
            expires_at=row[8],
            cancelled_at=row[9]
        )

    @staticmethod
    async def regenerate_daily_ai_processing() -> None:
        """
        Regenerate credits for all active subscriptions.
        Intended for use in daily scheduler/background task.
        """
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        async with DatabaseConnection() as db:
            try:
                subscription_rows = await db.fetch_all(
                    """
                    SELECT id, plan, expires_at, last_daily_regen FROM subscriptions
                    """,
                    raise_http=False
                )

                if not subscription_rows:
                    logger.info("[Scheduler] No active subscriptions to regenerate.")
                    return

                ai_processing_operation_rows = await db.fetch_all(
                    query="""
                    SELECT subscription_id, SUM(amount) as total_amount FROM ai_processing_operations
                    WHERE is_positive = 0 AND created_at > ?
                    GROUP BY subscription_id
                    """,
                    params=(day_ago, )
                )

                ai_processing_operation_dict = {subscription_id: total_sum for subscription_id, total_sum
                                                in ai_processing_operation_rows}
                batch_ai_usage_operation_params = []
                batch_subscription_update_params = []

                # updating status
                batch_subscription_status_update_params = []

                for subscription_id, plan, expires_at, last_daily_regen in subscription_rows:
                    if expires_at and now >= expires_at:
                        batch_subscription_status_update_params.append((subscription_id,))

                    if plan == "free-trial":
                        continue

                    if last_daily_regen and last_daily_regen >= day_ago:
                        continue

                    daily_regeneration = PLANS_CONFIG.get(plan, {}).get("daily_regeneration", 0)
                    if daily_regeneration <= 0:
                        continue

                    total_daily_usage = ai_processing_operation_dict.get(subscription_id, 0)
                    if total_daily_usage == 0:
                        continue

                    increment_value = (daily_regeneration if total_daily_usage >= daily_regeneration
                                       else daily_regeneration - total_daily_usage)

                    batch_ai_usage_operation_params.append((subscription_id, increment_value, True))
                    batch_subscription_update_params.append((increment_value, subscription_id))

                if not (batch_subscription_status_update_params or batch_subscription_update_params):
                    logger.info("[Scheduler] No updates or regenerations required.")
                    return

                # --- Main DB operations ---
                await db.execute_many(
                    query="UPDATE subscriptions SET status = 'expired' WHERE id = ?",
                    params_list=batch_subscription_status_update_params,
                    commit=False,
                    raise_http=False
                )

                await db.execute_many(
                    query="INSERT INTO ai_processing_operations (subscription_id, amount, is_positive) VALUES (?, ?, ?)",
                    params_list=batch_ai_usage_operation_params,
                    commit=False,
                    raise_http=False
                )

                await db.execute_many(
                    query="UPDATE subscriptions SET ai_processing = ai_processing + ? WHERE id = ?",
                    params_list=batch_subscription_update_params,
                    commit=False,
                    raise_http=False
                )

                # Commit once at the end
                await db.connection.commit()

                logger.info(f"[Scheduler] Regenerated ai_processing for {len(batch_subscription_update_params)} active subscriptions.")

            except Exception as e:
                # Roll back all operations if something failed
                await db.connection.rollback()
                logger.error(f"[Scheduler ERROR] Failed to regenerate subscriptions: {e}")

    @staticmethod
    async def regenerate_monthly_ai_processing() -> None:
        """
        Regenerate AI credits monthly for each active subscription based on their start date.
        Runs daily via background scheduler.
        """
        now = datetime.utcnow()
        async with DatabaseConnection() as db:
            try:
                # Select all active, non-expired subscriptions
                rows = await db.fetch_all(
                    """
                    SELECT id, plan, ai_processing, last_monthly_regen, started_at, expires_at
                    FROM subscriptions
                    WHERE status = 'active'
                      AND (expires_at IS NULL OR expires_at > ?)
                    """,
                    (now,),
                    raise_http=False
                )

                if not rows:
                    logger.warning("[Scheduler] No active subscriptions to regenerate.")
                    return

                updates = []
                insert_operations = []

                for row in rows:
                    subscription_id = row["id"]
                    plan = row["plan"]
                    last_monthly_regen = row["last_monthly_regen"]
                    started_at = row["started_at"]
                    expires_at = row["expires_at"]

                    # Skip if expired or cancelled
                    if expires_at and expires_at < now:
                        continue

                    # If subscription never regenerated, use started_at as reference
                    last_regen = last_monthly_regen or started_at

                    # If at least 1 month passed since last regeneration
                    if now >= last_regen + relativedelta(months=+1):
                        increment_value = PLANS_CONFIG.get(plan, {}).get("monthly_regeneration", 0)
                        if increment_value <= 0:
                            continue

                        updates.append((increment_value, now, subscription_id))
                        insert_operations.append((subscription_id, increment_value, True))

                if not updates:
                    logger.warning("[Scheduler] No subscriptions due for monthly regeneration.")
                    return

                # Add operation records
                await db.execute_many(
                    "INSERT INTO ai_usage_operations (subscription_id, amount, is_positive) VALUES (?, ?, ?)",
                    insert_operations,
                    commit=False,
                    raise_http=False
                )

                # Update balances and regeneration date
                await db.execute_many(
                    "UPDATE subscriptions SET ai_processing = ai_processing + ?, last_monthly_regen = ? WHERE id = ?",
                    updates,
                    commit=True,
                    raise_http=False
                )

                logger.info(f"[Scheduler] Regenerated {len(updates)} subscriptions for this period.")

            except Exception as e:
                await db.connection.rollback()
                logger.error(f"[Scheduler ERROR] Subscription regeneration failed: {e}")

    @staticmethod
    async def save_ai_usage_operation(user_id: str, amount: int = 1) -> None:
        """
        Records an AI usage operation and deducts from subscription balance atomically.
        Args:
            user_id (str): User ID.
            amount (int): Amount of AI usage to deduct.
        """
        async with DatabaseConnection() as db:
            try:
                # Check subscription balance
                sub_row = await db.fetch_one(
                    query="SELECT ai_processing, status, id FROM subscriptions WHERE user_id = ?",
                    params=(user_id,)
                )


                if not sub_row:
                    err_msg = f"[AIUsage] Subscription not found for user id: {user_id}"
                    logger.error(err_msg)
                    raise HTTPException(status_code=404, detail=err_msg)

                subscription_status = sub_row["status"]
                sub_id = sub_row["id"]
                if subscription_status != "active":
                    err_msg = "Subscription is not active"
                    logger.info(err_msg)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=err_msg
                    )

                balance = sub_row["ai_processing"]
                if balance < amount:
                    err_msg = f"[AIUsage] Insufficient AI balance for sub {sub_id}: {balance} < {amount}"
                    logger.warning(err_msg)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=err_msg
                    )

                # Perform insert and update as a single transaction
                await db.execute_one(
                    query="INSERT INTO ai_processing_operations (subscription_id, amount, is_positive) VALUES (?, ?, 0)",
                    params=(sub_id, amount),
                    commit=False
                )

                await db.execute_one(
                    query="UPDATE subscriptions SET ai_processing = ai_processing - ? WHERE id = ?",
                    params=(amount, sub_id),
                    commit=False
                )

                await db.connection.commit()
                logger.info(f"[AIUsage] Deducted {amount} credits from {sub_id} successfully")

            except Exception as e:
                if hasattr(db, "connection") and db.connection:
                    await db.connection.rollback()
                err_msg = f"[AIUsage ERROR] Failed to save usage for {sub_id}: {e}"
                logger.error(err_msg)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=err_msg
                )

    @staticmethod
    async def activate_subscription(user_id: str, plan: str, months: int) -> Subscription:
        """
        Activate or extend a subscription for the specified number of months.
        - If user is upgrading from free-trial, replace the subscription.
        - If extending or upgrading, add months to existing expiration.
        - If ai_processing < 0, reset credits; otherwise, add to existing balance.
        """
        current_subscription = await SubscriptionService.get_subscription(user_id)

        if not current_subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found for this user."
            )

        # Calculate new expiration date
        now = datetime.utcnow()
        reset_counter = current_subscription.ai_processing < 0
        current_plan = current_subscription.plan
        current_status = current_subscription.status

        # Determine new expiration date
        if current_plan == "free-trial" or current_status == "expired":
            # Starting fresh
            new_expires_at = now + relativedelta(months=months)
        elif current_subscription.expires_at and current_subscription.expires_at > now:
            # Extend current expiration
            new_expires_at = current_subscription.expires_at + relativedelta(months=months)
        else:
            # Expired or missing expires_at
            new_expires_at = now + relativedelta(months=months)


        ai_processing_amount = PLANS_CONFIG.get(plan, {}).get("monthly_regeneration", 0)
        if ai_processing_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan '{plan}' has invalid or missing regeneration settings."
            )

        async with DatabaseConnection() as db:
            try:
                if reset_counter:
                    await db.execute_one(
                        query="""
                            UPDATE subscriptions 
                            SET plan = ?, status = 'active', expires_at = ?, 
                                ai_processing = ?, cancelled_at = NULL
                            WHERE user_id = ?
                        """,
                        params=(plan, new_expires_at, ai_processing_amount, user_id),
                        commit=False,
                        raise_http=False
                    )
                else:
                    await db.execute_one(
                        query="""
                            UPDATE subscriptions 
                            SET plan = ?, status = 'active', 
                                ai_processing = ai_processing + ?, 
                                expires_at = ?, cancelled_at = NULL
                            WHERE user_id = ?
                        """,
                        params=(plan, ai_processing_amount, new_expires_at, user_id),
                        commit=False,
                        raise_http=False
                    )

                # Commit transaction
                await db.connection.commit()

                # Fetch updated subscription safely
                row = await db.fetch_one(
                    query="SELECT * FROM subscriptions WHERE user_id = ?",
                    params=(user_id,),
                    raise_http=False
                )
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Failed to retrieve updated subscription."
                    )

                subscription_id = row[0]
                # Perform update inside one transaction
                await db.execute_one(
                    query="INSERT INTO ai_processing_operations (subscription_id, is_positive, amount) VALUES (?, ?, ?)",
                    params=(subscription_id, True, ai_processing_amount),
                    raise_http=False
                )

                data = dict(row)
                logger.info(f"[Subscription] Activated or extended plan '{plan}' for user {user_id}")

                return Subscription(**data)

            except Exception as e:
                if hasattr(db, "connection") and db.connection:
                    await db.connection.rollback()
                err_msg = f"Error activating subscription for user {user_id}: {e}"
                logger.error(f"[Subscription ERROR] {err_msg}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=err_msg
                )

    @staticmethod
    async def activate_subscription_with_order(order_id: str, payment_data: dict) -> Subscription:
        """
        Activate subscription using a successfully paid order.
        Triggered by payment provider webhook after payment verification.
        """
        try:
            # Step 1. Verify payment data (signature, transaction, etc.)
            provider = payment_data.get("provider")
            transaction_id = payment_data.get("transaction_id")
            amount = float(payment_data.get("amount", 0))
            metadata = payment_data

            # Step 2. Retrieve and verify_service order
            order = await OrderService.get_order(order_id)
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )

            # Step 3. Prevent re-processing of already paid orders
            if order.status == "paid":
                logger.warning(f"[Webhook] Order {order_id} already paid, skipping duplicate activation.")
                return await SubscriptionService.get_subscription(order.user_id)

            # Step 4. Mark order as paid
            paid_order = await OrderService.mark_order_paid(
                order_id=order_id,
                transaction_id=transaction_id,
                payment_provider=provider,
                amount=amount,
                metadata=metadata
            )

            # Step 5. Activate or extend subscription
            subscription = await SubscriptionService.activate_subscription(
                user_id=paid_order.user_id,
                plan=paid_order.plan,
                months=paid_order.months
            )

            logger.info(
                f"[Webhook] Subscription activated for order {order_id} ({paid_order.plan}, {paid_order.months} mo)."
            )
            return subscription

        except HTTPException:
            # Pass through known HTTP exceptions (invalid order, etc.)
            raise
        except Exception as e:
            err = f"[Webhook ERROR] Activation failed for order {order_id}: {e}"
            logger.error(err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process payment webhook."
            )

    @staticmethod
    async def update_subscription(user_id: str, update_data: SubscriptionUpdate) -> Subscription:
        """Update user's subscription status"""
        async with DatabaseConnection() as db:
            # Build update query dynamically
            update_fields = []
            params = []

            if update_data.status is not None:
                update_fields.append("status = ?")
                params.append(update_data.status)

                if update_data.status == 'cancelled':
                    update_fields.append("cancelled_at = ?")
                    params.append(datetime.utcnow())

            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )

            params.append(user_id)
            update_query = f"UPDATE subscriptions SET {', '.join(update_fields)} WHERE user_id = ?"

            await db.execute_one(query=update_query, params=tuple(params))

            # Fetch updated subscription
            row = await db.fetch_one(
                query="SELECT * FROM subscriptions WHERE user_id = ?",
                params=(user_id,)
            )

        return Subscription(
            id=row[0],
            user_id=row[1],
            plan=row[2],
            status=row[3],
            ai_processing=row[4],
            last_monthly_regen=row[5],
            last_daily_regen=row[6],
            started_at=row[7],
            expires_at=row[8],
            cancelled_at=row[9]
        )


    @staticmethod
    def get_plan_limits(plan: str) -> dict:
        """Get limits for a specific plan"""
        return PLANS_CONFIG.get(plan, PLANS_CONFIG['free-trial'])

    @staticmethod
    async def check_subscription_active(user_id: str, raise_http: bool = True) -> bool:
        """Check if user has an active subscription"""
        subscription = await SubscriptionService.get_subscription(user_id)

        if not subscription:
            if raise_http:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subscription not found"
                )

            return False

        if subscription.status != 'active':
            if raise_http:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subscription is not active"
                )
            return False

        # Check if subscription has expired
        if subscription.expires_at and subscription.expires_at < datetime.utcnow():
            # Auto-expire the subscription
            await SubscriptionService.update_subscription(
                user_id,
                SubscriptionUpdate(status='expired')
            )
            if raise_http:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subscription is expired"
                )
            return False

        return True


    @staticmethod
    async def calculate_total_ai_processing_usage(sub_id: str, started_at: datetime) -> int:
        now = datetime.utcnow()

        # Calculate total difference in months across years
        months_diff = (now.year - started_at.year) * 12 + (now.month - started_at.month)

        # Shift started_at forward by that many months
        plan_current_month_started_time = started_at + relativedelta(months=months_diff)

        async with DatabaseConnection() as db:
            result = await db.fetch_one(
                query="""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM ai_processing_operations
                    WHERE subscription_id = ? AND created_at > ? AND is_positive = 0
                """,
                params=(sub_id, plan_current_month_started_time)
            )
        if result:
            return result[0]
        else:
            return 0

    @staticmethod
    async def get_plan_info(user_id: str) -> dict:
        """Get user's usage statistics"""
        subscription = await SubscriptionService.get_subscription(user_id)

        if not subscription:
            return {
                "used_credits": 0,
                "remaining_credits": 0,
                "monthly_regeneration": 0,
                "daily_regeneration": 0,
                "last_monthly_regen": None,
                "last_daily_regen": None
            }


        limits = SubscriptionService.get_plan_limits(subscription.plan)
        used_ai_processing = await SubscriptionService.calculate_total_ai_processing_usage(
            sub_id=subscription.id,
            started_at=subscription.started_at
        )

        subscription_info = await SubscriptionService.get_subscription(user_id)
        price = PRICING.get(subscription.plan, 0)

        return {
            "subscription_info": subscription_info,
            "used_credits": used_ai_processing,
            "remaining_credits": subscription.ai_processing,
            "monthly_regeneration": limits.get('monthly_regeneration', 0),
            "daily_regeneration": limits.get('daily_regeneration', 0),
            "last_monthly_regen": subscription.last_monthly_regen,
            "last_daily_regen": subscription.last_daily_regen,
            "price": price
        }