from fastapi import APIRouter, Request, HTTPException, Depends

from src.auth.auth import get_regos_token
from src.billing.subscription_service import SubscriptionService
from src.core.regos_api import regos_async_api_request
from src.core.security import get_current_user
from src.models.regos_additional import RegosBarcodeBatchAdd, RegosProductBatchEdit
from src.models.user import User

router = APIRouter(prefix="/regos", tags=["Regos"])

@router.post("/barcodes/batch")
async def batch_edit_regos_products(data: RegosBarcodeBatchAdd, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    integration_token = await get_regos_token(user_id=user_id)
    endpoint = "batch"
    filtered_data = data.dict(exclude_none=True)
    filtered_data["stop_on_error"] = False
    for req in filtered_data["requests"]:
        req["path"] = "Barcode/Add"

    result = await regos_async_api_request(
        endpoint=endpoint,
        request_data=filtered_data,
        token=integration_token
    )
    return result


@router.patch("/products/batch")
async def batch_edit_regos_products(data: RegosProductBatchEdit, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    integration_token = await get_regos_token(user_id=user_id)
    endpoint = "batch"
    filtered_data = data.dict(exclude_none=True)
    filtered_data["stop_on_error"] = False
    for req in filtered_data["requests"]:
        req["path"] = "Item/Edit"

    result = await regos_async_api_request(
        endpoint=endpoint,
        request_data=filtered_data,
        token=integration_token
    )
    return result


@router.post("/proxy/{endpoint:path}")
async def proxy_regos_request(endpoint: str, request: Request, current_user: User = Depends(get_current_user)):
    """
    Transparent proxy endpoint that forwards any JSON body
    to the corresponding Regos API path.
    """
    user_id = current_user.id
    await SubscriptionService.check_subscription_active(user_id)
    integration_token = await get_regos_token(user_id=user_id)

    try:
        data = await request.json()
    except Exception:
        data = {}

    result = await regos_async_api_request(
        endpoint=endpoint,
        request_data=data,
        token=integration_token
    )

    return result


