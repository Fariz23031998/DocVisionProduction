import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from src.core.conf import SESSION_EXPIRE_DAYS, DATABASE_URL
from src.models.user import Session


class SessionManager:
    @staticmethod
    async def create_session(user_id: str) -> Session:
        """Create a new session for a user"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(days=SESSION_EXPIRE_DAYS)

        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("""
                INSERT INTO sessions (session_id, user_id, created_at, last_activity, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, now, now, expires_at))
            await db.commit()

        return Session(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_activity=now,
            expires_at=expires_at
        )

    @staticmethod
    async def get_session(session_id: str) -> Optional[Session]:
        """Get session by ID"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT session_id, user_id, created_at, last_activity, expires_at
                FROM sessions WHERE session_id = ?
            """, (session_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Session(
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(
                            row['created_at'], str) else row['created_at'],
                        last_activity=datetime.fromisoformat(row['last_activity'].replace('Z', '+00:00')) if isinstance(
                            row['last_activity'], str) else row['last_activity'],
                        expires_at=datetime.fromisoformat(row['expires_at'].replace('Z', '+00:00')) if isinstance(
                            row['expires_at'], str) else row['expires_at']
                    )
        return None

    @staticmethod
    async def update_activity(session_id: str) -> bool:
        """Update last activity time for a session"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            cursor = await db.execute("""
                UPDATE sessions SET last_activity = ? WHERE session_id = ?
            """, (datetime.utcnow(), session_id))
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """Delete a session"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            cursor = await db.execute("""
                DELETE FROM sessions WHERE session_id = ?
            """, (session_id,))
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def delete_user_sessions(user_id: str) -> int:
        """Delete all sessions for a user"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            cursor = await db.execute("""
                DELETE FROM sessions WHERE user_id = ?
            """, (user_id,))
            await db.commit()
            return cursor.rowcount

    @staticmethod
    async def cleanup_expired_sessions() -> int:
        """Remove sessions that haven't been active for 10 days"""
        cutoff_time = datetime.utcnow() - timedelta(days=SESSION_EXPIRE_DAYS)

        async with aiosqlite.connect(DATABASE_URL) as db:
            cursor = await db.execute("""
                DELETE FROM sessions 
                WHERE last_activity < ?
            """, (cutoff_time,))
            await db.commit()
            return cursor.rowcount

    @staticmethod
    async def get_active_sessions_count() -> int:
        """Get count of active sessions"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            async with db.execute("SELECT COUNT(*) FROM sessions") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0