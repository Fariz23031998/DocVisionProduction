import smtplib
import random
import string
import asyncio
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import BackgroundTasks, HTTPException, status
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple
import threading
import logging

from src.utils.helper import format_message_from_template
from src.core.conf import SMTP_SERVER, SMTP_PORT, APP_NAME, EMAIL_FROM, EMAIL_PASSWORD


# Uncomment if you want to use Redis for production
# import redis
# import json
logger = logging.getLogger("DocVision")


class SMTPVerifyService:
    """
    Email verification service for FastAPI applications.

    This class provides functionality to send verification codes via email
    and verify_service them. It supports both in-memory storage (for development)
    and Redis storage (for production).

    Features:
    - Thread-safe in-memory code storage
    - Automatic cleanup of expired codes
    - FastAPI HTTPException integration
    - Background task support
    - Configurable verification code length and expiration

    Attributes:
        verification_config (dict): Configuration settings loaded from JSON
        email (str): SMTP email address
        password (str): SMTP password
        smtp_server (str): SMTP server address
        smtp_port (int): SMTP server port
        app_name (str): Application name for email templates
        verification_data (Dict[str, Dict]): In-memory storage for verification codes
    """

    def __init__(self):
        """
        Initialize the Verify class with configuration settings.

        Loads configuration from JSON file and starts the cleanup task
        for expired verification codes.
        """
        self.email = EMAIL_FROM
        self.password = EMAIL_PASSWORD
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.app_name = APP_NAME

        # Thread-safe in-memory storage (consider Redis for production)
        self.verification_data: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Start cleanup task
        self._start_cleanup_task()

        # For production, use Redis instead:
        # self.redis_client = redis.Redis(host='localhost', port=6379, db=0)

    def generate_verification_code(self, length: int = 6) -> str:
        """
        Generate a random numeric verification code.

        Args:
            length (int, optional): Length of the verification code. Defaults to 6.

        Returns:
            str: Random numeric verification code

        Example:
            >>> verify_service = SMTPVerifyService()
            >>> code = verify_service.generate_verification_code(4)
            >>> len(code)
            4
        """
        return ''.join(random.choices(string.digits, k=length))

    def _send_verification_email_sync(
            self,
            recipient_email: str,
            verification_code: str,
            subject: str = "Email Verification Code"
    ) -> Tuple[bool, str]:
        """
        Send verification email synchronously (internal use only).

        Args:
            recipient_email (str): Recipient's email address
            verification_code (str): The verification code to send
            subject (str, optional): Email subject line

        Returns:
            Tuple[bool, str]: (Success status, Message)

        Raises:
            Various SMTP exceptions that are caught and returned as tuple
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = recipient_email
            msg['Subject'] = subject

            # Email body
            html_body = format_message_from_template(verification_code=verification_code, app_name=self.app_name)
            msg.attach(MIMEText(html_body, 'html'))

            # Create SMTP session
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email, self.password)

            # Send email
            text = msg.as_string()
            server.sendmail(self.email, recipient_email, text)
            server.quit()

            logger.info(f"Verification email sent successfully to {recipient_email}")
            return True, "Verification code sent successfully!"

        except smtplib.SMTPAuthenticationError as e:
            logger.info(f"SMTP Authentication failed: {str(e)}")
            return False, "Authentication failed. Check email credentials."
        except smtplib.SMTPRecipientsRefused as e:
            logger.info(f"Invalid recipient: {str(e)}")
            return False, "Invalid recipient email address."
        except smtplib.SMTPException as e:
            logger.info(f"SMTP error: {str(e)}")
            return False, f"SMTP error occurred: {str(e)}"
        except Exception as e:
            logger.info(f"Unexpected error: {str(e)}")
            return False, f"An error occurred: {str(e)}"

    async def send_verification_email_async(
            self,
            send_to: str,
            subject: str = "Email Verification Code"
    ) -> Dict[str, any]:
        """
        Send verification email asynchronously.

        Args:
            send_to (str): Recipient's email address
            subject (str, optional): Email subject line

        Returns:
            Dict[str, any]: Response with success status, message, and verification code

        Raises:
            HTTPException: 500 if email sending fails
            HTTPException: 422 if email format is invalid

        Example:
            # >>> verify_service = Verify()
            # >>> result = await verify_service.send_verification_email_async("user@example.com")
            # >>> result["success"]
            True
        """
        # Basic email validation
        if not send_to or "@" not in send_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format"
            )

        verification_code = self.generate_verification_code()

        # Store code immediately (before sending email)
        expires_at = int(time.time()) + 600  # 10 minutes

        with self._lock:
            self.verification_data[send_to] = {
                "code": verification_code,
                "expires_at": expires_at,
                "created_at": int(time.time())
            }

        # For production with Redis:
        # await self._store_verification_code_redis(recipient_email, verification_code, expires_at)

        # Send email in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            success, message = await loop.run_in_executor(
                executor,
                self._send_verification_email_sync,
                send_to,
                verification_code,
                subject
            )

        if not success:
            # Remove the stored code since email failed
            with self._lock:
                self.verification_data.pop(send_to, None)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification email: {message}"
            )

        return {
            "success": True,
            "message": message,
            "email": send_to,
            "expires_in_minutes": 10
        }

    def send_verification_background(
            self,
            background_tasks: BackgroundTasks,
            recipient_email: str,
            subject: str = "Email Verification Code"
    ) -> Dict[str, any]:
        """
        Send verification email using FastAPI background tasks (recommended).

        Args:
            background_tasks (BackgroundTasks): FastAPI background tasks instance
            recipient_email (str): Recipient's email address
            subject (str, optional): Email subject line

        Returns:
            Dict[str, any]: Response with success status and message

        Raises:
            HTTPException: 422 if email format is invalid

        Example:
            >>> from fastapi import BackgroundTasks
            >>> verify_service = SMTPVerifyService()
            >>> result = verify_service.send_verification_background(background_tasks, "user@example.com")
            >>> result["success"]
            True
        """
        # Basic email validation
        if not recipient_email or "@" not in recipient_email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format"
            )

        verification_code = self.generate_verification_code()
        expires_at = int(time.time()) + 600  # 10 minutes

        # Store code immediately
        with self._lock:
            self.verification_data[recipient_email] = {
                "code": verification_code,
                "expires_at": expires_at,
                "created_at": int(time.time())
            }

        # Add email sending to background tasks
        background_tasks.add_task(
            self._send_verification_email_sync,
            recipient_email,
            verification_code,
            subject
        )

        return {
            "success": True,
            "message": "Verification code is being sent",
            "email": recipient_email,
            "expires_in_minutes": 10
        }

    def handle_sending_verification(
            self,
            send_to: str,
            background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, any]:
        """
        Handle sending verification with automatic method selection.

        Chooses between background tasks (preferred) or async method based on
        whether BackgroundTasks is provided.

        Args:
            send_to (str): Recipient's email address
            background_tasks (Optional[BackgroundTasks]): FastAPI background tasks

        Returns:
            Dict[str, any]: Response with success status and message

        Raises:
            HTTPException: Various HTTP exceptions based on the chosen method

        Example:
            >>> verify_service = SMTPVerifyService()
            >>> result = verify_service.handle_sending_verification("user@example.com", background_tasks)
            >>> result["success"]
            True
        """
        if background_tasks:
            return self.send_verification_background(background_tasks, send_to)
        else:
            # Fallback to async version
            logger.info("Warning: No background tasks provided, using async method")
            return asyncio.run(self.send_verification_email_async(send_to))

    def get_verification_code(self, sent_to: str) -> Dict[str, any]:
        """
        Retrieve stored verification code for an email address.

        Args:
            sent_to (str): Email address to check

        Returns:
            Dict[str, any]: Response with verification code if valid

        Raises:
            HTTPException: 404 if no code found or expired
            HTTPException: 422 if email format is invalid

        Example:
            >>> verify_service = SMTPVerifyService()
            >>> result = verify_service.get_verification_code("user@example.com")
            >>> result["verification_code"]
            "123456"
        """
        if not sent_to or "@" not in sent_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format"
            )

        with self._lock:
            if sent_to not in self.verification_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No verification code has been sent to this email address"
                )

            code_data = self.verification_data[sent_to]
            if code_data["expires_at"] < int(time.time()):
                # Clean up expired code
                del self.verification_data[sent_to]
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="The verification code has expired. Please request a new one"
                )

            return {
                "success": True,
                "message": "Verification code found",
                "verification_code": code_data["code"],
                "expires_at": code_data["expires_at"],
                "created_at": code_data["created_at"]
            }

    def verify_code(self, sent_to: str, provided_code: str) -> Dict[str, any]:
        """
        Verify if the provided code matches the stored verification code.

        Args:
            sent_to (str): Email address that received the code
            provided_code (str): Code provided by the user

        Returns:
            Dict[str, any]: Response with verification result

        Raises:
            HTTPException: 404 if no code found
            HTTPException: 410 if code expired
            HTTPException: 400 if code is invalid
            HTTPException: 422 if email format is invalid

        Example:
            >>> verify_service = SMTPVerifyService()
            >>> result = verify_service.verify_code("user@example.com", "123456")
            >>> result["success"]
            True
        """
        if not sent_to or "@" not in sent_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format"
            )

        if not provided_code or not provided_code.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Verification code cannot be empty"
            )

        with self._lock:
            if sent_to not in self.verification_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No verification code found for this email address"
                )

            code_data = self.verification_data[sent_to]
            if code_data["expires_at"] < int(time.time()):
                del self.verification_data[sent_to]
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Verification code has expired. Please request a new one"
                )

            if code_data["code"] == provided_code.strip():
                # Code is correct, remove it (one-time use)
                del self.verification_data[sent_to]
                return {
                    "success": True,
                    "message": "Email verification successful!",
                    "email": sent_to
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code. Please check and try again"
                )

    def _cleanup_expired_codes(self) -> None:
        """
        Remove expired verification codes from memory.

        This method is called periodically by the cleanup thread to
        maintain memory efficiency by removing expired codes.
        """
        current_time = int(time.time())
        with self._lock:
            expired_keys = [
                key for key, value in self.verification_data.items()
                if value["expires_at"] < current_time
            ]
            for key in expired_keys:
                del self.verification_data[key]
                logger.info(f"Cleaned up expired verification code for {key}")

    def _start_cleanup_task(self) -> None:
        """
        Start background thread to clean up expired codes every 5 minutes.

        Creates a daemon thread that runs continuously to clean up
        expired verification codes, preventing memory leaks.
        """

        def cleanup_loop():
            while True:
                time.sleep(300)  # 5 minutes
                self._cleanup_expired_codes()

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about stored verification codes.

        Returns:
            Dict[str, any]: Statistics including total codes, expired codes, etc.

        Example:
            >>> verify_service = SMTPVerifyService()
            >>> stats = verify_service.get_stats()
            >>> stats["total_codes"]
            5
        """
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
                "timestamp": current_time
            }

    def clear_all_codes(self) -> Dict[str, any]:
        """
        Clear all verification codes from memory (admin function).

        Returns:
            Dict[str, any]: Response with count of cleared codes

        Warning:
            This will clear ALL verification codes. Use with caution.

        Example:
            >>> verify_service = SMTPVerifyService()
            >>> result = verify_service.clear_all_codes()
            >>> result["cleared_count"]
            10
        """
        with self._lock:
            cleared_count = len(self.verification_data)
            self.verification_data.clear()
            logger.info(f"Cleared {cleared_count} verification codes from memory")

            return {
                "success": True,
                "message": "All verification codes cleared",
                "cleared_count": cleared_count
            }