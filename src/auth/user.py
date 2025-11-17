import re
import uuid
from datetime import datetime
from typing import Optional
import aiosqlite
from fastapi import HTTPException, status
import logging

from src.core.conf import DATABASE_URL
from src.models.user import UserCreateRegos, User, UserUpdate, UserCreate
from src.utils.helper import validate_password
from src.auth.auth import AuthService

logger = logging.getLogger("DocVision")

FAKE_HASH = "$2b$12$C/Ut9wB4N8GQf8jh0EOYEePUE/vZfnH4RKqGx1LncRHCp/Itg1heg"


class UserService:
    @staticmethod
    async def generate_username(db, base: str):
        # Normalize base (remove spaces, lowercase, etc. — optional)
        base = base.strip().replace(" ", "")
        base = re.sub(r'[^a-zA-Z0-9]', '', base.lower())[:15]
        username = base
        counter = 1

        while True:
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (username,)
            )
            exists = await cursor.fetchone()

            if not exists:
                return username

            username = f"{base}{counter}"
            counter += 1

    @staticmethod
    async def create_user(user_data: UserCreate | UserCreateRegos, username_gen_type: str = "email") -> User:
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
        email = user_data.email
        full_name = user_data.full_name

        async with aiosqlite.connect(DATABASE_URL) as db:
            try:
                if username_gen_type == "email":
                    username = await UserService.generate_username(db, email.split("@")[0])
                else:
                    username = await UserService.generate_username(db, full_name)

                await db.execute("""
                    INSERT INTO users (id, username, email, phone, full_name, password_hash, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, username, email, user_data.phone, full_name, hashed_password, True, now))
                await db.commit()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error: {e}"
                )

        return User(
            id=user_id,
            username=username,
            email=email,
            phone=user_data.phone,
            full_name=full_name,
            is_active=True,
            created_at=now
        )

    @staticmethod
    async def update_user(user_data: UserUpdate):
        """Update a user"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            try:
                await db.execute("""
                    UPDATE users SET full_name = ?, username = ? WHERE id = ?
                """, (user_data.full_name, user_data.username, user_data.id ))
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
    async def authenticate_user(login: str, password: str) -> Optional[User]:
        """Authenticate user with secure comparison"""

        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row

            # Determine login type
            if "@" in login:
                field = "email"
            elif login.replace("+", "").isdigit():
                field = "phone"
            else:
                field = "username"

            query = f"""
                SELECT id, username, email, phone, full_name, password_hash, is_active, created_at
                FROM users 
                WHERE {field} = ? AND is_active = TRUE
            """

            async with db.execute(query, (login,)) as cursor:
                row = await cursor.fetchone()

            if not row:
                # prevent timing attack
                AuthService.verify_password(password, FAKE_HASH)
                return None

            if not AuthService.verify_password(password, row['password_hash']):
                return None

            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                phone=row['phone'],
                full_name=row['full_name'],
                is_active=row['is_active'],
                created_at=row['created_at']
            )

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, username, email, phone, full_name, is_active, created_at
                FROM users WHERE id = ? AND is_active = TRUE
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        id=row['id'],
                        username=row['username'],
                        email=row['email'],
                        phone=row["phone"],
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

    @staticmethod
    async def get_user_by_phone(phone: str) -> Optional[User]:
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, username, email, phone, full_name, is_active, created_at
                FROM users WHERE phone = ? AND is_active = TRUE
            """, (phone,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        id=row['id'],
                        username=row['username'],
                        email=row['email'],
                        phone=row["phone"],
                        full_name=row['full_name'],
                        is_active=row['is_active'],
                        created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(
                            row['created_at'], str) else row['created_at']
                    )
        return None