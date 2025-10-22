import bcrypt
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import HTTPException, status
from jose import JWTError, jwt

from src.core.conf import SESSION_EXPIRE_DAYS, SECRET_KEY, ALGORITHM
from src.core.db import DatabaseConnection
from src.utils.helper import decrypt_token


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """
        Verify a plaintext password against its bcrypt hash.

        This method uses bcrypt's secure comparison function which includes
        constant-time comparison to prevent timing attacks and properly
        handles salt verification.

        Args:
            password (str): The plaintext password to verify_service
            hashed (str): The bcrypt hash string to verify_service against

        Returns:
            bool: True if the password matches the hash, False otherwise

        Raises:
            ValueError: If the hashed parameter is not a valid bcrypt hash
            UnicodeEncodeError: If password contains characters that cannot be UTF-8 encoded

        Example:
            >>> hashed_pw = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4w8nPv2K4e"
            >>> AuthService.verify_password("mypassword", hashed_pw)
            True
            >>> AuthService.verify_password("wrongpassword", hashed_pw)
            False

        Note:
            The password parameter should be the raw plaintext password.
            The hashed parameter should be a complete bcrypt hash string
            including the algorithm identifier, cost factor, salt, and hash.
        """
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    @staticmethod
    def create_access_token(user_id: str, session_id: str) -> str:
        """Create a JWT access token"""
        expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRE_DAYS)
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "exp": expires_at,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            if "expired" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials"
                )



async def get_regos_token(user_id: str) -> str:
    """
    Retrieve and decrypt Regos tokens for a specific user.

    This function fetches token from the core for a given user ID,
    validates the response, and decrypts sensitive token information.

    Args:
        user_id (str): The unique identifier for the user whose tokens to retrieve.

    Returns:
        str: string containing regos token

    """

    async with DatabaseConnection() as db:
        # This will raise HTTPException automatically if not found or on error
        regos_tokens = await db.fetch_one(
            query="SELECT integration_token FROM regos_tokens WHERE user_id = ?",
            params=(user_id,)
        )

    # Convert Row to dict and decrypt sensitive fields
    decrypted_token = decrypt_token(regos_tokens[0])

    return decrypted_token

async def email_exists(email: str) -> bool:
    async with DatabaseConnection() as db:
        result = await db.fetch_one(
            "SELECT 1 FROM users WHERE email = ?",
            (email,),
            allow_none=True
        )
    return result is not None