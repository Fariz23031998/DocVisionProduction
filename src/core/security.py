from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.auth import AuthService
from src.models.user import User
from src.auth.session import SessionManager
from src.auth.user import UserService
from src.core.conf import SESSION_EXPIRE_DAYS

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency to get current authenticated user"""
    try:
        # Decode the token
        payload = AuthService.decode_token(credentials.credentials)
        user_id = payload.get("user_id")
        session_id = payload.get("session_id")

        if not user_id or not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Check if session exists and is valid
        session = await SessionManager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found"
            )

        # Check if session has expired (10 days of inactivity)
        if datetime.utcnow() - session.last_activity > timedelta(days=SESSION_EXPIRE_DAYS):
            await SessionManager.delete_session(session_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired due to inactivity"
            )

        # Get user
        user = await UserService.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Update session activity
        await SessionManager.update_activity(session_id)

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


# Helper function to get session ID from token
async def get_session_id_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract session ID from token"""
    payload = AuthService.decode_token(credentials.credentials)
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    return session_id