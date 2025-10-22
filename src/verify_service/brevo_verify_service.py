import random
import string
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple
import requests
from fastapi import BackgroundTasks, HTTPException, status
import logging

from src.utils.helper import format_message_from_template
from src.core.conf import (
    APP_NAME,
    BREVO_API_KEY,
    BREVO_SENDER_EMAIL,
    BREVO_SENDER_NAME,
    BREVO_BASE_URL,
)

logger = logging.getLogger("DocVision")


class BrevoVerify:
    """
    Email verification service using Brevo (Sendinblue) transactional API.

    Designed to plug into FastAPI the same way as the existing SMTP-based
    verification flow. Stores verification codes in-memory (thread-safe) with
    background cleanup. For production, consider persisting in a core or Redis.
    """

    def __init__(self):
        # Brevo config
        self.app_name = APP_NAME
        self.api_key = BREVO_API_KEY
        self.sender_email = BREVO_SENDER_EMAIL
        self.sender_name = BREVO_SENDER_NAME or self.app_name
        self.base_url = (BREVO_BASE_URL or "https://api.brevo.com/v3").rstrip("/")

        # In-memory store and lock
        self.verification_data: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Start cleanup task
        self._start_cleanup_task()

    @staticmethod
    def generate_verification_code(length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))

    def _send_verification_email_sync(
        self,
        recipient_email: str,
        verification_code: str,
        subject: str = "Email Verification Code",
    ) -> Tuple[bool, str]:
        """
        Send an email via Brevo v3 API (synchronous).
        """
        if not self.api_key:
            logger.info("Brevo API key is not configured")
            return False, "Brevo API key is not configured"

        if not self.sender_email:
            logger.info("Brevo sender email is not configured")
            return False, "Brevo sender email is not configured"

        html_body = format_message_from_template(
            verification_code=verification_code,
            app_name=self.app_name,
        )

        url = f"{self.base_url}/smtp/email"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self.api_key,
        }
        payload = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": html_body,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if 200 <= resp.status_code < 300:
                logger.info(f"Brevo verification email sent to {recipient_email}")
                return True, "Verification code sent successfully!"
            else:
                try:
                    error_msg = resp.json()
                except Exception:
                    error_msg = resp.text
                logger.info(
                    f"Brevo send failed ({resp.status_code}): {error_msg}"
                )
                return False, f"Brevo send failed: {resp.status_code}"
        except requests.Timeout:
            logger.info("Brevo request timed out")
            return False, "Brevo request timed out"
        except requests.RequestException as e:
            logger.info(f"Brevo request error: {str(e)}")
            return False, f"Brevo request error: {str(e)}"

    async def send_verification_email_async(
        self,
        send_to: str,
        subject: str = "Email Verification Code",
    ) -> Dict[str, any]:
        if not send_to or "@" not in send_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format",
            )

        verification_code = self.generate_verification_code()
        expires_at = int(time.time()) + 600  # 10 minutes

        with self._lock:
            self.verification_data[send_to] = {
                "code": verification_code,
                "expires_at": expires_at,
                "created_at": int(time.time()),
            }

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            success, message = await loop.run_in_executor(
                executor,
                self._send_verification_email_sync,
                send_to,
                verification_code,
                subject,
            )

        if not success:
            with self._lock:
                self.verification_data.pop(send_to, None)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification email: {message}",
            )

        return {
            "success": True,
            "message": message,
            "email": send_to,
            "expires_in_minutes": 10,
        }

    def send_verification_background(
        self,
        background_tasks: BackgroundTasks,
        recipient_email: str,
        subject: str = "Email Verification Code",
    ) -> Dict[str, any]:
        if not recipient_email or "@" not in recipient_email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format",
            )

        verification_code = self.generate_verification_code()
        expires_at = int(time.time()) + 600  # 10 minutes

        with self._lock:
            self.verification_data[recipient_email] = {
                "code": verification_code,
                "expires_at": expires_at,
                "created_at": int(time.time()),
            }

        background_tasks.add_task(
            self._send_verification_email_sync,
            recipient_email,
            verification_code,
            subject,
        )

        return {
            "success": True,
            "message": "Verification code is being sent",
            "email": recipient_email,
            "expires_in_minutes": 10,
        }

    def handle_sending_verification(
        self,
        send_to: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, any]:
        if background_tasks:
            return self.send_verification_background(background_tasks, send_to)
        else:
            return asyncio.run(self.send_verification_email_async(send_to))

    def get_verification_code(self, sent_to: str) -> Dict[str, any]:
        if not sent_to or "@" not in sent_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format",
            )

        with self._lock:
            if sent_to not in self.verification_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No verification code found for this email address",
                )

            code_data = self.verification_data[sent_to]
            if code_data["expires_at"] < int(time.time()):
                del self.verification_data[sent_to]
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Verification code has expired. Please request a new one",
                )

            return {
                "success": True,
                "email": sent_to,
                "verification_code": code_data["code"],
                "expires_at": code_data["expires_at"],
            }

    def verify_code(self, sent_to: str, provided_code: str) -> Dict[str, any]:
        if not sent_to or "@" not in sent_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format",
            )

        if not provided_code or not provided_code.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Verification code cannot be empty",
            )

        with self._lock:
            if sent_to not in self.verification_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No verification code found for this email address",
                )

            code_data = self.verification_data[sent_to]
            if code_data["expires_at"] < int(time.time()):
                del self.verification_data[sent_to]
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Verification code has expired. Please request a new one",
                )

            if code_data["code"] == provided_code.strip():
                del self.verification_data[sent_to]
                return {
                    "success": True,
                    "message": "Email verification successful!",
                    "email": sent_to,
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code. Please check and try again",
                )

    def _cleanup_expired_codes(self) -> None:
        current_time = int(time.time())
        with self._lock:
            expired_keys = [
                key for key, value in self.verification_data.items()
                if value["expires_at"] < current_time
            ]
            for key in expired_keys:
                del self.verification_data[key]
                logger.info(f"Brevo cleanup expired verification code for {key}")

    def _start_cleanup_task(self) -> None:
        def cleanup_loop():
            while True:
                time.sleep(300)  # 5 minutes
                self._cleanup_expired_codes()

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def get_stats(self) -> Dict[str, any]:
        current_time = int(time.time())
        with self._lock:
            total_codes = len(self.verification_data)
            expired_codes = sum(
                1 for code_data in self.verification_data.values()
                if code_data["expires_at"] < current_time
            )
            active_codes = total_codes - expired_codes

            return {
                "total_codes": total_codes,
                "active_codes": active_codes,
                "expired_codes": expired_codes,
                "timestamp": current_time,
            }

    def clear_all_codes(self) -> Dict[str, any]:
        with self._lock:
            cleared_count = len(self.verification_data)
            self.verification_data.clear()
            logger.info(
                f"Brevo cleared {cleared_count} verification codes from memory"
            )
            return {
                "success": True,
                "message": "All verification codes cleared",
                "cleared_count": cleared_count,
            }

