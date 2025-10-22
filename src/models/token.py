from pydantic import BaseModel


class RegosTokenCreateUpdate(BaseModel):
    integration_token: str

class RegosToken(BaseModel):
    token_id: int
    user_id: str
    token_name: str
    regos_api_login: str
    regos_session_id: str
    regos_token: str
    regos_app_key: str
