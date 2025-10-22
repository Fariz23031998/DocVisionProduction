# Models
from datetime import datetime
from typing import Literal
from pydantic import EmailStr, BaseModel


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    verification_code: str

class UserUpdate(BaseModel):
    id: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

class Session(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
    user: User

class VerificationData(BaseModel):
    email: EmailStr
    type: Literal["register", "reset_password"] = "register"

class ResetPassword(BaseModel):
    email: EmailStr
    verification_code: str
    new_password: str

class ChangePassword(BaseModel):
    old_password: str
    new_password: str