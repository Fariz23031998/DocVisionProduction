from fastapi import APIRouter, Depends

from src.auth.auth import get_regos_token
from src.core.db import DatabaseConnection
from src.core.security import get_current_user
from src.models.token import RegosTokenCreateUpdate
from src.models.user import User
from src.utils.helper import encrypt_token

router = APIRouter(prefix="/tokens", tags=["Tokens"])

@router.post("/regos/upsert")
async def upsert_regos_token(token_data: RegosTokenCreateUpdate, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    integration_token = token_data.integration_token
    encrypted_token = encrypt_token(integration_token)
    async with DatabaseConnection() as db:
        # This will raise HTTPException automatically on error
        result = await db.execute_one(
            query="""
                INSERT INTO regos_tokens (user_id, integration_token) 
                VALUES (?, ?)
                ON CONFLICT(user_id) 
                DO UPDATE SET integration_token = excluded.integration_token
            """,
            params=(user_id, encrypted_token)
        )

    return {
        "message": "Token created or updated successfully",
        "rows_affected": result["rows_affected"]
    }

@router.post("/regos")
async def add_regos_token(token_data: RegosTokenCreateUpdate, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    integration_token = token_data.integration_token
    encrypted_token = encrypt_token(integration_token)
    async with DatabaseConnection() as db:
        # This will raise HTTPException automatically on error
        result = await db.execute_one(
            query="INSERT INTO regos_tokens (user_id, integration_token) VALUES (?, ?)",
            params=(user_id, encrypted_token)
        )

    return {
        "message": "Token created successfully",
        "token_id": result["inserted_row_id"],
        "rows_affected": result["rows_affected"]
    }


@router.patch("/regos")
async def update_regos_token(data: RegosTokenCreateUpdate, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    encrypted_token = encrypt_token(data.integration_token)
    async with DatabaseConnection() as db:
        # This will raise HTTPException automatically on error
        result = await db.execute_one(
            query="UPDATE regos_tokens SET integration_token = ? WHERE user_id = ?",
            params=(encrypted_token, user_id)
        )

    return {
        "message": "Token updated successfully",
        "rows_affected": result["rows_affected"]
    }


@router.get("/regos")
async def read_regos_token(current_user: User = Depends(get_current_user)):
    return await get_regos_token(user_id=current_user.id)


@router.delete("/regos")
async def delete_token(current_user: User = Depends(get_current_user)):
    async with DatabaseConnection() as db:
        # This will raise HTTPException automatically on error
        result = await db.execute_one(
            query="DELETE FROM regos_tokens WHERE user_id = ?",
            params=(current_user.id, )
        )

    return {
        "message": "Token deleted successfully",
        "rows_affected": result["rows_affected"]
    }
