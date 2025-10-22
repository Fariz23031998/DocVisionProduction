import logging
from datetime import datetime

from src.auth.session import SessionManager
from src.billing.order_service import OrderService
from src.billing.subscription_service import SubscriptionService


logger = logging.getLogger("DocVision")

async def regenerate_credits_daily():
    """Job: regenerate AI credits for all active subscriptions."""
    start_time = datetime.utcnow().isoformat()
    logger.info(f"[Scheduler] Regeneration started at {start_time}")

    try:
        await SubscriptionService.regenerate_daily_ai_processing()
        logger.info(f"[Scheduler] Regeneration completed successfully at {datetime.utcnow().isoformat()}")
    except Exception as e:
        logger.error(f"[Scheduler ERROR] {e}")

async def regenerate_monthly():
    """Runs monthly to regenerate subscription-based AI processing."""
    try:
        logger.info(f"[Scheduler] Monthly regeneration started at {datetime.utcnow().isoformat()}")
        await SubscriptionService.regenerate_monthly_ai_processing()
        logger.info("[Scheduler] Monthly regeneration completed successfully.")
    except Exception as e:
        logger.error(f"[Scheduler ERROR] Monthly regeneration failed: {e}")


async def cleanup_sessions_hourly():
    """Runs every hour to clean up expired user sessions."""
    try:
        deleted_count = await SessionManager.cleanup_expired_sessions()
        if deleted_count > 0:
            logger.error(f"[Scheduler] Cleaned up {deleted_count} expired sessions at {datetime.utcnow().isoformat()}")
        else:
            logger.info(f"[Scheduler] No expired sessions to clean up at {datetime.utcnow().isoformat()}")
    except Exception as e:
        logger.error(f"[Scheduler ERROR] Session cleanup failed: {e}")

async def cleanup_expired_orders_hourly():
    """Runs every hour to mark old unpaid orders as expired."""
    try:
        expired_count = await OrderService.expire_old_orders()
        if expired_count > 0:
            logger.info(f"[Scheduler] Expired {expired_count} old unpaid orders at {datetime.utcnow().isoformat()}")
        else:
            logger.info(f"[Scheduler] No expired orders found at {datetime.utcnow().isoformat()}")
    except Exception as e:
        logger.error(f"[Scheduler ERROR] Order expiration failed: {e}")
