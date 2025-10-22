from datetime import datetime

from fastapi import APIRouter

from src.auth.session import SessionManager
from src.auth.user import UserService
from src.core.conf import DATABASE_URL, SESSION_EXPIRE_DAYS

router = APIRouter()

@router.get("/api/sessions/cleanup")
async def manual_cleanup():
    """Manually trigger session cleanup (admin endpoint)"""
    deleted_count = await SessionManager.cleanup_expired_sessions()
    return {
        "message": f"Cleaned up {deleted_count} expired sessions",
        "deleted_count": deleted_count
    }


@router.get("/api/health")
async def health_check():
    """Health check endpoint"""
    active_sessions = await SessionManager.get_active_sessions_count()
    total_users = await UserService.get_users_count()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "core": "aiosqlite",
        "database_file": DATABASE_URL,
        "active_sessions": active_sessions,
        "total_users": total_users
    }

@router.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    active_sessions = await SessionManager.get_active_sessions_count()
    total_users = await UserService.get_users_count()

    return {
        "active_sessions": active_sessions,
        "total_users": total_users,
        "session_expire_days": SESSION_EXPIRE_DAYS,
        "database_file": DATABASE_URL
    }