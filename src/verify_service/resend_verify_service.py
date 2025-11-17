import asyncio
from datetime import datetime, timedelta
import logging
from random import randint

from fastapi import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_429_TOO_MANY_REQUESTS
import resend

from src.core.conf import RESEND_API_KEY, RESEND_EMAIL_FROM, APP_NAME
from src.core.db import DatabaseConnection
from src.utils.helper import load_template_from_txt, format_message_from_template

logger = logging.getLogger("DocVision")

# Set Resend API key
resend.api_key = RESEND_API_KEY

HTML_TEMPLATE = load_template_from_txt()
VERIFICATION_EMAIL = F"no-reply@{RESEND_EMAIL_FROM}"

async def add_code_into_db(recipient: str):
    async with DatabaseConnection() as db:
        code = str(randint(100000, 999999))
        ten_min_ago = datetime.utcnow() - timedelta(minutes=0)
        last_code = await db.fetch_one(
            query="SELECT created_at FROM verification_codes WHERE created_at > ? AND recipient = ?",
            params=(ten_min_ago, recipient),
            raise_http=False,
        )

        if last_code:
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait 3 minutes before requesting another code.",
            )

        await db.execute_one(
            query="INSERT INTO verification_codes (recipient, code, created_at) VALUES (?, ?, ?)",
            params=(recipient, code, datetime.utcnow()),
            commit=True,
            raise_http=True
        )

        return code


async def send_verification_code(recipient_email: str, code: str):
    for i in range(5):
        try:
            html_body = format_message_from_template(
                template_content=HTML_TEMPLATE,
                verification_code=code,
                app_name=APP_NAME
            )

            params: resend.Emails.SendParams = {
                "from": VERIFICATION_EMAIL,  # e.g., "onboarding@yourdomain.com"
                "to": [recipient_email],
                "subject": f"{APP_NAME} - Verification Code",
                "html": html_body,
            }

            # Use asyncio.to_thread to run sync Resend API in async context
            email: resend.Email = await asyncio.to_thread(
                resend.Emails.send,
                params
            )

            logger.info(f"Verification email sent to {recipient_email}, ID: {email.get('id')}")
            return {"ok": True, "result": "Email sent", "email_id": email.get("id")}

        except Exception as e:
            logger.error(f"Attempt {i + 1} failed: {e}")
            await asyncio.sleep(1)

    return {"ok": False, "error": "Failed to send after 5 attempts."}


async def check_verification_code(recipient_email: str, code: str):
    async with DatabaseConnection() as db:
        ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
        result = await db.fetch_one(
            query="SELECT 1 FROM verification_codes WHERE created_at > ? AND recipient = ? AND code = ?",
            params=(ten_min_ago, recipient_email, code),
        )
        if not bool(result):
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Verification code not found."
            )


async def clean_verification_data():
    async with DatabaseConnection() as db:
        ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
        result = await db.execute_one(
            query="DELETE FROM verification_codes WHERE created_at < ?",
            params=(ten_min_ago,),
            commit=True,
            raise_http=False
        )
        # Assuming result has rowcount or similar attribute
        deleted_count = getattr(result, 'rowcount', 0) if result else 0
        logger.info(f"Deleted {deleted_count} records")