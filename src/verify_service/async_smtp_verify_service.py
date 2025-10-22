import asyncio
from datetime import datetime, timedelta
from email.message import EmailMessage
import aiosmtplib
import logging
from random import randint

from fastapi import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_429_TOO_MANY_REQUESTS

from src.core.conf import SMTP_SERVER, SMTP_PORT, SMTP_EMAIL_FROM, SMTP_EMAIL_PASSWORD, APP_NAME
from src.core.db import DatabaseConnection
from src.utils.helper import load_template_from_txt, format_message_from_template

logger = logging.getLogger("DocVision")

html_template = load_template_from_txt()

async def add_code_into_db(recipient: str):
    async with DatabaseConnection() as db:
        code = str(randint(100000, 999999))
        ten_min_ago = datetime.utcnow() - timedelta(minutes=3)
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
            html_body = format_message_from_template(template_content=html_template, verification_code=code,
                                                     app_name=APP_NAME)

            message = EmailMessage()
            message["From"] = SMTP_EMAIL_FROM
            message["To"] = recipient_email
            message["Subject"] = APP_NAME
            message.add_alternative(html_body, subtype="html")

            await aiosmtplib.send(
                message,
                hostname=SMTP_SERVER,
                port=SMTP_PORT,
                start_tls=True,
                username=SMTP_EMAIL_FROM,
                password=SMTP_EMAIL_PASSWORD,
            )
            logger.info(f"Verification email sent to {recipient_email}")
            return {"ok": True, "result": "Email sent"}
        except Exception as e:
            logger.error(f"Attempt {i+1} failed: {e}")
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
            params=(ten_min_ago, ),
            commit=True,
            raise_http=False
        )
        logger.info(f"Deleted {len} records")

