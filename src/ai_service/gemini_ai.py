import asyncio
import json
import logging
import os
import google.generativeai as genai
from PIL import Image
from fastapi import HTTPException
from google.api_core.exceptions import GoogleAPIError
from starlette.status import HTTP_400_BAD_REQUEST

from src.ai_service.ai_helper import extract_text_from_pdf
from src.core.conf import GEMINI_API_KEY
from src.ai_service.prompt import AI_PROMPT_EXCEL_COLUMN_MAPPING, prompt_common_rules, \
    AI_PROMPT_PDF_COLUMN_MAPPING, AI_PROMPT_PDF_UNSTRUCTURED_EXTRACTION, prompt_header_image
from src.utils.helper import write_json_file
from src.utils.pdf_extractor import extract_pdf_tables_to_tuples, parse_string_to_list, map_ai_response_to_dicts

logger = logging.getLogger("DocVision")

# Configure API
genai.configure(api_key=GEMINI_API_KEY)

# Initialize model
model = genai.GenerativeModel("gemini-2.5-flash")


async def extract_data(file_path: str) -> dict:
    """
    Async function to extract data from PDF or image file.

    Args:
        file_path: Path to the PDF or image file

    Returns:
        Extracted data as dictionary

    Raises:
        ValueError: If file format is not supported
        FileNotFoundError: If file doesn't exist
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    # Supported image formats
    image_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif']

    try:
        if ext == '.pdf':
            # Process PDF
            result = await asyncio.to_thread(_extract_from_pdf, file_path)
        elif ext in image_formats:
            prompt = f"{prompt_header_image}{prompt_common_rules}"
            # Process Image
            result = await asyncio.to_thread(_extract_from_image, file_path, prompt)
        else:
            err_msg = f"Unsupported file format: {ext}. Supported formats: PDF, {', '.join(image_formats)}"
            logger.error(err_msg)
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=err_msg
            )

        if not result:
            err_msg = "Ai model couldn't process data."
            logger.error(err_msg)
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=err_msg
            )

        return {"ok": True, "message": "success", "data": result}

    except Exception as e:
        err_msg = f"Error processing file {file_path}: {str(e)}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=err_msg
        )

async def detect_excel_columns_gemini(
    excel_text: str,
    prompt: str = AI_PROMPT_EXCEL_COLUMN_MAPPING,
    model_name: str = "gemini-2.5-flash"
) -> dict:
    """
    Uses Gemini 2.5 Flash to detect and map Excel columns from given text data.

    Args:
        prompt (str): Instruction text for the model.
        excel_text (str): Top rows of Excel formatted as plain text.
        model_name (str): Gemini model name (default: gemini-2.5-flash).

    Returns:
        dict: Parsed JSON result with columns, irrelevant_columns, irrelevant_rows.
    """

    user_prompt = f"{prompt}\n\nHere are the top rows from the Excel file:\n\n{excel_text}"

    try:
        model_instance = genai.GenerativeModel(model_name)
        response = await asyncio.to_thread(
            model_instance.generate_content,
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                response_mime_type="application/json"
            )
        )

        # Extract text result
        result_text = response.text.strip() if response.text else ""

        try:
            result = json.loads(result_text)
            return {"ok": True, "result": result}

        except json.JSONDecodeError:
            logger.warning("⚠️ Warning: Gemini returned invalid JSON, returning raw text.")
            return {"ok": False, "error": result_text}

    except GoogleAPIError as e:
        logger.error(f"❌ Gemini API error: {e}")
        return {"ok": False, "error": str(e)}

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return {"ok": False, "error": str(e)}


def _extract_from_image(image_path: str, prompt: str) -> str:
    """Helper function to extract data from image"""
    img = Image.open(image_path)
    response = model.generate_content([prompt, img])
    return parse_string_to_list(response.text)

def _extract_from_pdf(pdf_path: str) -> list:
    """Helper function to extract structured or unstructured data from PDF."""
    rows_as_list_of_tuples = extract_pdf_tables_to_tuples(pdf_path)
    rows_length = len(rows_as_list_of_tuples)

    # 1️⃣ No tables detected — use unstructured extraction
    if rows_length == 0:
        pdf_content = extract_text_from_pdf(pdf_path)
        prompt = f"""{AI_PROMPT_PDF_UNSTRUCTURED_EXTRACTION}
Here's unstructured data as text:
{pdf_content[:5000]}
"""
        try:
            response = model.generate_content([prompt])
            result = (response.text or "").strip()
            return parse_string_to_list(result)
        except Exception as e:
            logger.error(f"Unstructured extraction failed: {e}")
            return []

    # 2️⃣ Many rows — send only top/bottom parts
    if rows_length > 15:
        prompt = f"""{AI_PROMPT_PDF_COLUMN_MAPPING}
Here's top 10 rows from the PDF data:
{"\n".join(str(row) for row in rows_as_list_of_tuples[:10])}
Here's bottom 5 rows from the PDF data:
{"\n".join(str(row) for row in rows_as_list_of_tuples[-5:])}
"""
    else:
        # 3️⃣ Small dataset — send all rows
        prompt = f"""{AI_PROMPT_PDF_COLUMN_MAPPING}
Here's PDF data:
{"\n".join(str(row) for row in rows_as_list_of_tuples)}
"""

    # 4️⃣ Send prompt to model
    try:
        response = model.generate_content([prompt])
        eval_response = parse_string_to_list((response.text or "").strip())
        if not eval_response:
            return []

        result = map_ai_response_to_dicts(table_rows=rows_as_list_of_tuples, ai_response=eval_response)
        return result
    except Exception as e:
        logger.error(f"Structured extraction failed: {e}")
        return []



