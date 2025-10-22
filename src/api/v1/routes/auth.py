from fastapi import HTTPException, APIRouter, Depends, BackgroundTasks
from fastapi import status

from src.auth.auth import AuthService, email_exists
from src.auth.session import SessionManager
from src.auth.user import UserService
from src.core.db import DatabaseConnection
from src.core.security import get_current_user, get_session_id_from_token
from src.billing.subscription_service import SubscriptionService
from src.models.user import TokenResponse, UserCreate, UserLogin, User, ResetPassword, ChangePassword, VerificationData
from src.verify_service.async_smtp_verify_service import check_verification_code, send_verification_code, \
    add_code_into_db

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    await check_verification_code(user_data.email, user_data.verification_code)

    """Register a new user"""
    user = await UserService.create_user(user_data)

    # Create 7-day free trial for new user
    await SubscriptionService.create_subscription(user.id, plan='free-trial')

    session = await SessionManager.create_session(user.id)
    token = AuthService.create_access_token(user.id, session.session_id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_at=session.expires_at,
        user=user
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin):
    """Login user"""
    user = await UserService.authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    session = await SessionManager.create_session(user.id)
    token = AuthService.create_access_token(user.id, session.session_id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_at=session.expires_at,
        user=user
    )


@router.post("/logout")
async def logout(
        current_user: User = Depends(get_current_user),
        session_id: str = Depends(get_session_id_from_token)
):
    """Logout user (delete current session)"""
    deleted = await SessionManager.delete_session(session_id)
    if deleted:
        return {"message": "Logged out successfully"}
    else:
        return {"message": "Session not found"}


@router.post("/logout-all")
async def logout_all(current_user: User = Depends(get_current_user)):
    """Logout from all devices (delete all user sessions)"""
    deleted_count = await SessionManager.delete_user_sessions(current_user.id)
    return {
        "message": f"Logged out from {deleted_count} sessions",
        "deleted_sessions": deleted_count
    }

@router.post("/reset-password")
async def reset_password(data: ResetPassword):
    email = data.email
    verification_code = data.verification_code
    new_password = data.new_password

    await check_verification_code(email, verification_code)

    return await UserService.change_password(email, new_password)


@router.post("/change-password")
async def change_password(data: ChangePassword, current_user: User = Depends(get_current_user)):
    """Reset user password after verifying the old password."""
    user_id = current_user.id

    # Dummy hash for timing attack prevention
    dummy_hash = "$2b$12$dummy.hash.to.prevent.timing.attacks.value"

    async with DatabaseConnection() as db:
        row = await db.fetch_one(
            query="SELECT password_hash FROM users WHERE id = ?",
            params=(user_id,),
            allow_none=True
        )

    if row is None:
        # User doesn't exist - use dummy hash to maintain constant timing
        AuthService.verify_password(data.old_password, dummy_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )

    stored_hash = row[0]  # or row['password_hash'] depending on your DB wrapper

    if not AuthService.verify_password(data.old_password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )

    return await UserService.change_password(
        email=current_user.email,
        password=data.new_password
    )

@router.post("/send-verification-code", status_code=200)
async def send_verification_code_route(verification_data: VerificationData, background_tasks: BackgroundTasks):
    email = verification_data.email
    verification_type = verification_data.type
    is_email_exists = await email_exists(email)

    if is_email_exists and verification_type == "register":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )

    if not is_email_exists and verification_type == "reset_password":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account found for this email address"
        )
    code = await add_code_into_db(recipient=email)
    background_tasks.add_task(send_verification_code, email, code)
    return {"ok": True, "message": "Verification code sent"}