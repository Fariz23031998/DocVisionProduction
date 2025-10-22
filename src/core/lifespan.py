from contextlib import asynccontextmanager
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

from src.core.db import DatabaseConnection
from src.core.dependencies import regenerate_credits_daily, regenerate_monthly, cleanup_sessions_hourly, \
    cleanup_expired_orders_hourly
from src.utils.helper import delete_all_files
from src.verify_service.async_smtp_verify_service import clean_verification_data

scheduler = AsyncIOScheduler()
database_connection = DatabaseConnection()
logger = logging.getLogger("DocVision")


@asynccontextmanager
async def lifespan(app):
    # Initialize core
    await database_connection.init_db()
    logger.info("Database initialized")

    # --- Startup phase ---
    scheduler.start()

    # Run every day at 00:05 AM
    scheduler.add_job(
        regenerate_credits_daily,
        CronTrigger(hour=0, minute=5),
        id="daily_ai_regeneration",
        replace_existing=True
    )
    logger.info("[Lifespan] APScheduler started; daily regeneration job added.")

    # Run monthly on the 1st day of the month at 00:10 local time
    scheduler.add_job(
        regenerate_monthly,
        CronTrigger(day=1, hour=0, minute=10),
        id="monthly_ai_regeneration",
        replace_existing=True
    )
    logger.info("[Lifespan] APScheduler started; monthly regeneration jobs added.")

    # Hourly cleanup at every full hour
    scheduler.add_job(
        cleanup_sessions_hourly,
        CronTrigger(minute=0),
        id="session_cleanup",
        replace_existing=True
    )

    logger.info("[Lifespan] APScheduler started; session cleanup jobs added.")

    # Hourly delete invoice files
    scheduler.add_job(
        delete_all_files,
        'interval',
        hours=1,
        args=["uploads"]
    )

    logger.info("[Lifespan] All uploaded files deleted")

    scheduler.add_job(
        clean_verification_data,
        CronTrigger(minute=0),
        id="verification_cleanup",
        replace_existing=True
    )
    logger.info("[Lifespan] APScheduler started; verification data cleanup jobs added.")

    # Order expiration every hour (at minute 5)
    scheduler.add_job(
        cleanup_expired_orders_hourly,
        CronTrigger(minute=5),
        id="order_expiration",
        replace_existing=True
    )

    logger.info("[Lifespan] APScheduler started; expired orders cleanup jobs added.")


    logger.info("Cleanup and regeneration tasks started")

    yield

    # Cancel the cleanup tasks
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("[Lifespan] APScheduler stopped.")
