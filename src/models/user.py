# Models
from datetime import datetime
from typing import Literal
from pydantic import EmailStr, BaseModel, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    phone: str = ""
    password: str
    full_name: str
    verification_code: str

class UserCreateRegos(BaseModel):
    phone: str
    email: str = ""
    password: str
    full_name: str


class UserUpdate(BaseModel):
    id: str
    full_name: str | None = None
    username: str | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        # 1. Require at least full_name or username
        if not self.full_name and not self.username:
            raise ValueError("Either full_name or username must be provided")

        # 2. Validate username rules ONLY if username is provided
        if self.username is not None:
            if len(self.username) < 7:
                raise ValueError("Username must be at least 7 characters long")

            if not any(ch.isalpha() for ch in self.username):
                raise ValueError("Username must contain at least one letter")

        return self


class UserLogin(BaseModel):
    login: str
    password: str

class User(BaseModel):
    id: str
    username: str
    email: str = ""
    phone: str = ""
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

class DeleteUserRequest(BaseModel):
    email: EmailStr
    code: str
