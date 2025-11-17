from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from src.auth.user import UserService
from src.core.conf import ADMIN_CODE
from src.core.db import DatabaseConnection
from src.core.security import get_current_user
from src.models.user import User, UserUpdate, DeleteUserRequest

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@router.patch("/me")
async def update_current_user_info(data: UserUpdate, current_user: User = Depends(get_current_user)):
    result = await UserService.update_user(user_data=data)
    return result


@router.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    """Example protected route"""
    return {
        "message": f"Hello {current_user.full_name}, this is a protected route!",
        "user_id": current_user.id,
        "timestamp": datetime.utcnow()
    }

@router.post("/users/delete")
async def delete_user(data: DeleteUserRequest):
    if ADMIN_CODE != data.code:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Incorrect information"
        )

    async with DatabaseConnection() as db:
        await db.execute_one("PRAGMA foreign_keys = ON")
        await db.execute_one(
            "DELETE FROM users WHERE email = ?",
            (data.email,),
            commit=True,
            raise_http=True
        )

    return {"ok": True, "message": "User deleted"}

