from datetime import datetime
from fastapi import APIRouter, Depends

from src.auth.user import UserService
from src.core.security import get_current_user
from src.models.user import User, UserUpdate

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

