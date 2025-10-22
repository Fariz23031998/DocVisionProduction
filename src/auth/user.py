import uuid
from datetime import datetime
from typing import Optional
import aiosqlite
from fastapi import HTTPException, status
import logging

from src.core.conf import DATABASE_URL
from src.models.user import UserCreate, User, UserUpdate
from src.utils.helper import validate_password
from src.auth.auth import AuthService

logger = logging.getLogger("DocVision")


class UserService:
    @staticmethod
    async def create_user(user_data: UserCreate) -> User:
        """Create a new user"""
        user_id = str(uuid.uuid4())
        password = user_data.password
        is_password_valid = validate_password(password=password)
        if not is_password_valid["ok"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=is_password_valid["desc"]
            )
        hashed_password = AuthService.hash_password(user_data.password)
        now = datetime.utcnow()

        async with aiosqlite.connect(DATABASE_URL) as db:
            try:
                await db.execute("""
                    INSERT INTO users (id, email, full_name, password_hash, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, user_data.email, user_data.full_name, hashed_password, True, now))
                await db.commit()
            except aiosqlite.IntegrityError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

        return User(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=True,
            created_at=now
        )

    @staticmethod
    async def update_user(user_data: UserUpdate):
        """Update a user"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            try:
                await db.execute("""
                    UPDATE users SET full_name = ? WHERE id = ?
                """, (user_data.full_name, user_data.id ))
                await db.commit()
                return {"ok": True, "message": "User successfully updated"}

            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error updating user: {e}"
                )



    @staticmethod
    async def change_password(email: str, password: str) -> dict:
        hashed_password = AuthService.hash_password(password)
        async with aiosqlite.connect(DATABASE_URL) as db:
            try:
                await db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed_password, email))
                await db.commit()
            except aiosqlite.IntegrityError:
                err_msg = f"{email} already registered"
                logger.info(err_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=err_msg
                )
            except Exception as e:
                err_msg = f"error: {e}"
                logger.error(err_msg)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=err_msg
                )

        return {"ok": True, "email": email}

    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, email, full_name, password_hash, is_active, created_at
                FROM users WHERE email = ? AND is_active = TRUE
            """, (email,)) as cursor:
                row = await cursor.fetchone()
                if row and AuthService.verify_password(password, row['password_hash']):
                    return User(
                        id=row['id'],
                        email=row['email'],
                        full_name=row['full_name'],
                        is_active=row['is_active'],
                        created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(
                            row['created_at'], str) else row['created_at']
                    )
        return None

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, email, full_name, is_active, created_at
                FROM users WHERE id = ? AND is_active = TRUE
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        id=row['id'],
                        email=row['email'],
                        full_name=row['full_name'],
                        is_active=row['is_active'],
                        created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(
                            row['created_at'], str) else row['created_at']
                    )
        return None

    @staticmethod
    async def get_users_count() -> int:
        """Get total count of active users"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0