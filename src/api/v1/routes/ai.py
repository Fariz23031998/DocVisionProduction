from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status

from src.ai_service.gemini_ai import extract_data, detect_excel_columns_gemini
from src.ai_service.open_ai import convert_file_to_json_async, detect_excel_columns
from src.billing.subscription_service import SubscriptionService
from src.core.conf import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from src.core.security import get_current_user
from src.models.ai import ExcelColumnDetectionResponse, DetectColumnName
from src.models.user import User
from src.utils.helper import compress_file

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/invoice-file-upload")
async def invoice_file_upload(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...)
):
    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed. Allowed: {ALLOWED_EXTENSIONS}")

    # Read the file content
    content = await file.read()
    file_size = len(content)

    # Compress if too large
    if file_size > MAX_FILE_SIZE:
        content = await compress_file(content, file_extension)
        compressed_size = len(content)
        if compressed_size > MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large even after compression (>{MAX_FILE_SIZE} bytes)")

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    custom_filename = f"upload_{timestamp}{file_extension}"
    file_path = f"uploads/{custom_filename}"
    Path("uploads").mkdir(exist_ok=True)

    # Save file
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    user_id = current_user.id
    # check ai_processing
    await SubscriptionService.save_ai_usage_operation(user_id=user_id)

    # Run extraction logic
    result = await extract_data(file_path=file_path)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "File conversion failed")
        )

    return result

@router.post("/detect-column-names", response_model=ExcelColumnDetectionResponse)
async def detect_column_names(data: DetectColumnName, current_user: User = Depends(get_current_user)):
    # check ai_processing
    user_id = current_user.id
    await SubscriptionService.save_ai_usage_operation(user_id=user_id)

    top_rows = data.top_rows
    # result = await detect_excel_columns(excel_text=top_rows)
    result = await detect_excel_columns_gemini(excel_text=top_rows)
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Something went wrong")
        )

    return result