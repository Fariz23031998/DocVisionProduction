from pydantic import BaseModel, Field


class RegosTokenCreateUpdate(BaseModel):
    token: str = Field(..., min_length=32, max_length=32)

class RegosAuthToken(BaseModel):
    token: str = Field(..., min_length=32, max_length=32)

class RegosToken(BaseModel):
    token_id: int
    user_id: str
    token_name: str
    regos_api_login: str
    regos_session_id: str
    regos_token: str
    regos_app_key: str
