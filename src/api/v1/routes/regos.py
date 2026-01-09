import logging

from fastapi import APIRouter, Request, Depends, HTTPException

from src.auth.auth import get_regos_token
from src.billing.subscription_service import SubscriptionService
from src.core.regos_api import regos_async_api_request
from src.core.security import get_current_user
from src.models.regos_additional import RegosBarcodeBatchAdd, RegosProductBatchEdit
from src.models.user import User
from src.core.db import DatabaseConnection
from src.core.redis_client import redis_client


logger = logging.getLogger("DocVision")
REDIS_TTL_SECONDS = 86400
PURCHASE_DOCUMENT_DELETE_ACTIONS = {"DocPurchaseDeleted", "DocPurchaseDeleteMarked", "DocPurchasePerformed"}
PURCHASE_DOCUMENT_UPDATE_ACTIONS = {"DocPurchaseAdded", "DocPurchaseEdited", "DocPurchasePerformCanceled"}
router = APIRouter(prefix="/regos", tags=["Regos"])

async def check_regos_token(token):
    async with DatabaseConnection() as db:
        result = await db.fetch_one(
            query="SELECT 1 FROM regos_tokens WHERE integration_token=?",
            params=(token,),
            raise_http=True
        )
        logger.warning(f"webhook's token: {result}")
        return result[0]



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


import json

@router.post("/webhook")
async def handle_regos_webhook(request: Request):
    body = await request.json()

    webhook_token = body.get("connected_integration_id")
    if not webhook_token:
        raise HTTPException(status_code=400, detail="Missing integration token")

    if not await check_regos_token(webhook_token):
        raise HTTPException(status_code=401, detail="Invalid integration token")

    webhook_data = body.get("data", {})
    event_type = webhook_data.get("action")
    event_payload = webhook_data.get("data", {})

    if event_type not in PURCHASE_DOCUMENT_DELETE_ACTIONS and event_type not in PURCHASE_DOCUMENT_UPDATE_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid action")

    doc_id = event_payload.get("id", 0)

    base_key = f"regos:purchase:{webhook_token}"
    last_version_key = f"{base_key}:last_version"
    updated_zset_key = f"{base_key}:updated_ids"
    deleted_zset_key = f"{base_key}:deleted_ids"

    # Atomic version increment
    current_version = redis_client.incr(last_version_key)

    if event_type in PURCHASE_DOCUMENT_UPDATE_ACTIONS:
        # Add to updated set with version as score
        redis_client.zadd(updated_zset_key, {doc_id: current_version})
        # Remove from deleted set if exists
        redis_client.zrem(deleted_zset_key, doc_id)
    else:
        # Add to deleted set with version as score
        redis_client.zadd(deleted_zset_key, {doc_id: current_version})
        # Remove from updated set if exists
        redis_client.zrem(updated_zset_key, doc_id)

    # Set TTL for cleanup
    redis_client.expire(last_version_key, REDIS_TTL_SECONDS)
    redis_client.expire(updated_zset_key, REDIS_TTL_SECONDS)
    redis_client.expire(deleted_zset_key, REDIS_TTL_SECONDS)

    return {"ok": True, "version": current_version}


@router.get("/doc-purchase/version/{version}")
async def get_doc_purchase_version(
    version: int,
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id
    integration_token = await get_regos_token(user_id=user_id)

    base_key = f"regos:purchase:{integration_token}"
    last_version_key = f"{base_key}:last_version"
    updated_zset_key = f"{base_key}:updated_ids"
    deleted_zset_key = f"{base_key}:deleted_ids"

    backend_latest = redis_client.get(last_version_key)
    backend_latest = int(backend_latest) if backend_latest else 0

    # Frontend ahead → full sync
    if version > backend_latest:
        return {
            "full_sync": True,
            "updated_ids": [],
            "deleted_ids": [],
            "latest_version": backend_latest
        }

    # Incremental fetch using ZSET score
    updated_ids = redis_client.zrangebyscore(updated_zset_key, version + 1, backend_latest)
    deleted_ids = redis_client.zrangebyscore(deleted_zset_key, version + 1, backend_latest)

    return {
        "full_sync": False,
        "updated_ids": list(map(int, updated_ids)),
        "deleted_ids": list(map(int, deleted_ids)),
        "latest_version": backend_latest
    }


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


