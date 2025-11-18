import asyncio
import io
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from PIL import Image
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
import logging

from src.ai_service.gemini_ai import extract_data, detect_excel_columns_gemini, ai_match_products
from src.billing.subscription_service import SubscriptionService
from src.core.conf import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from src.core.security import get_current_user
from src.models.ai import DetectColumnName, AIMatchRequest
from src.models.user import User
from src.utils.helper import compress_file

logger = logging.getLogger("DocVision")
router = APIRouter(prefix="/ai", tags=["AI"])


def normalize_mpo_to_jpeg(file_content: bytes) -> bytes:
    img = Image.open(io.BytesIO(file_content))
    img.seek(0)  # first frame
    output = io.BytesIO()
    img.save(output, format="JPEG")
    return output.getvalue()


async def invoice_upload_stream(
        file_content: bytes,
        file_extension: str,
        current_user: User
) -> AsyncGenerator[str, None]:
    """Stream processing updates for invoice upload"""

    try:
        # Step 1: Validate file extension
        yield f"data: {json.dumps({'status': 'validating', 'message': 'Checking file type...'})}\n\n"

        if file_extension not in ALLOWED_EXTENSIONS:
            yield f"data: {json.dumps({'status': 'error', 'message': f'File type not allowed. Allowed: {ALLOWED_EXTENSIONS}'})}\n\n"
            return

        # Step 2: Check size (15%)
        yield f"data: {json.dumps({'status': 'checking_size', 'message': 'Checking file size...'})}\n\n"
        if file_extension == ".mpo":
            file_content = normalize_mpo_to_jpeg(file_content)
            file_extension = ".jpg"

        file_size = len(file_content)
        # Step 3: Compress if needed (25%)
        if file_size > MAX_FILE_SIZE:
            yield f"data: {json.dumps({'status': 'compressing', 'message': 'File too large, compressing...'})}\n\n"

            file_content = await compress_file(file_content, file_extension)
            compressed_size = len(file_content)

            if compressed_size > MAX_FILE_SIZE:
                yield f"data: {json.dumps({'status': 'error', 'message': f'File too large even after compression (>{MAX_FILE_SIZE} bytes)'})}\n\n"
                return

        # Step 4: Save file (35%)
        yield f"data: {json.dumps({'status': 'saving', 'message': 'Saving file...'})}\n\n"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        custom_filename = f"upload_{timestamp}{file_extension}"
        file_path = f"uploads/{custom_filename}"
        Path("uploads").mkdir(exist_ok=True)

        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        # Step 5: Check subscription (45%)
        yield f"data: {json.dumps({'status': 'checking_subscription', 'message': 'Checking AI usage...'})}\n\n"

        user_id = current_user.id
        usage_result = await SubscriptionService.save_ai_usage_operation(user_id=user_id)
        # Check if the operation failed
        if not usage_result.get("ok"):
            error_message = usage_result.get("message", "Failed to check AI usage")
            error_code = usage_result.get("code", 500)
            yield f"data: {json.dumps({'status': 'error', 'message': error_message, "error_code": error_code})}\n\n"
            return  # Break SSE stream - STOPS HERE

        # Step 6: Extract data - START (55%)
        yield f"data: {json.dumps({'status': 'extracting', 'message': 'Extracting data with AI...'})}\n\n"

        # Step 7: Extract data - IN PROGRESS (70%)
        yield f"data: {json.dumps({'status': 'processing', 'message': 'AI is analyzing your document...'})}\n\n"

        task = asyncio.create_task(extract_data(file_path=file_path))

        while not task.done():
            yield f"data: {json.dumps({'status': 'keepalive', 'message': 'ИИ обрабатывает документы...'})}\n\n"

            # Wait up to 5 seconds for task to complete
            done, pending = await asyncio.wait([task], timeout=5.0)

            if done:
                break

        result = await task

        if not result.get("ok"):
            yield f"data: {json.dumps({'status': 'error', 'message': result.get('message', 'File conversion failed')})}\n\n"
            return

        # Step 8: Post-processing (85%)
        yield f"data: {json.dumps({'status': 'finalizing', 'message': 'Finalizing results...'})}\n\n"

        # Small delay to show the status
        await asyncio.sleep(0.5)

        # Step 9: Success (100%)
        yield f"data: {json.dumps({'status': 'completed', 'result': result})}\n\n"

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in invoice_upload_stream: {error_details}")
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

async def detect_columns_stream(
        top_rows: str,
        current_user: User
) -> AsyncGenerator[str, None]:
    """Stream processing updates for column detection"""
    try:
        # Step 1: Check subscription
        yield f"data: {json.dumps({'status': 'checking_subscription', 'message': 'Checking AI usage...'})}\n\n"

        user_id = current_user.id
        usage_result = await SubscriptionService.save_ai_usage_operation(user_id=user_id)
        # Check if the operation failed
        if not usage_result.get("ok"):
            error_message = usage_result.get("message", "Failed to check AI usage")
            error_code = usage_result.get("code", 500)
            yield f"data: {json.dumps({'status': 'error', 'message': error_message, "error_code": error_code})}\n\n"
            return  # Break SSE stream - STOPS HERE

        # Step 2: Detect columns (this is the AI operation)
        yield f"data: {json.dumps({'status': 'detecting', 'message': 'Analyzing columns with AI...'})}\n\n"

        task = asyncio.create_task(detect_excel_columns_gemini(excel_text=top_rows))

        while not task.done():
            yield f"data: {json.dumps({'status': 'keepalive', 'message': 'ИИ обрабатывает документы...'})}\n\n"

            # Wait up to 5 seconds for task to complete
            done, pending = await asyncio.wait([task], timeout=5.0)

            if done:
                break

        result = await task

        if not result.get("ok"):
            yield f"data: {json.dumps({'status': 'error', 'message': result.get('error', 'Something went wrong')})}\n\n"
            return

        # Step 3: Success
        yield f"data: {json.dumps({'status': 'completed', 'result': result})}\n\n"

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in detect_columns_stream: {error_details}")
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

async def ai_match_products_stream(
        not_matched_items: str,
        found_result: str,
        current_user: User
) -> AsyncGenerator[str, None]:
    """Stream processing updates for match products"""
    try:
        # Step 1: Check subscription
        yield f"data: {json.dumps({'status': 'checking_subscription', 'message': 'Checking AI usage...'})}\n\n"

        user_id = current_user.id
        usage_result = await SubscriptionService.save_ai_usage_operation(user_id=user_id)
        # Check if the operation failed
        if not usage_result.get("ok"):
            error_message = usage_result.get("message", "Failed to check AI usage")
            error_code = usage_result.get("code", 500)
            yield f"data: {json.dumps({'status': 'error', 'message': error_message, "error_code": error_code})}\n\n"
            return  # Break SSE stream - STOPS HERE

        # Step 2: Detect columns (this is the AI operation)
        yield f"data: {json.dumps({'status': 'detecting', 'message': 'Analyzing unmatched products with AI...'})}\n\n"

        task = asyncio.create_task(ai_match_products(not_matched_items, found_result))

        while not task.done():
            yield f"data: {json.dumps({'status': 'keepalive', 'message': 'ИИ обрабатывает сопоставление продуктов...'})}\n\n"

            # Wait up to 5 seconds for task to complete
            done, pending = await asyncio.wait([task], timeout=5.0)

            if done:
                break

        result = await task

        if not result:
            yield f"data: {json.dumps({'status': 'error', 'message': result.get('error', 'Something went wrong')})}\n\n"
            return

        # Step 3: Success
        yield f"data: {json.dumps({'status': 'completed', 'result': result})}\n\n"

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in detect_columns_stream: {error_details}")
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

@router.post("/invoice-file-upload")
async def invoice_file_upload(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...)
):
    file_content = await file.read()
    file_extension = Path(file.filename).suffix.lower()

    # Now pass the content to the stream generator
    return StreamingResponse(
        invoice_upload_stream(file_content, file_extension, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/detect-column-names")
async def detect_column_names(
        data: DetectColumnName,
        current_user: User = Depends(get_current_user)
):
    """Detect column names with SSE streaming"""

    # Extract data before streaming
    top_rows = data.top_rows

    return StreamingResponse(
        detect_columns_stream(top_rows, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/match")
async def match_products_with_ai(data: AIMatchRequest, current_user: User = Depends(get_current_user)):
    logger.info(f"data: {data}")
    return StreamingResponse(
        ai_match_products_stream(data.not_matched_items, data.found_result, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )