import asyncio
import aiofiles
import os
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
from openai import AsyncOpenAI, OpenAIError
import logging

from src.core.conf import OPENAI_API_KEY
from src.ai_service.ai_helper import get_file_type, extract_text_from_excel, extract_text_from_pdf
from src.ai_service.prompt import create_prompt, AI_PROMPT_EXCEL_COLUMN_MAPPING


logger = logging.getLogger("DocVision")

# Initialize async client
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Thread pool for CPU-intensive operations
thread_pool = ThreadPoolExecutor(max_workers=4)


async def convert_file_to_json_async(file_path: str, user_request: Optional[str] = None) -> Dict[str, Any]:
    """
    Async version: Convert an image, PDF, or Excel file into JSON format.

    Args:
        file_path (str): Path to the file (image, PDF, or Excel).
        user_request (str): Additional user request to customize prompt.
    Returns:
        dict: Extracted JSON-like structure.
    """
    try:
        # Check if file exists (non-blocking)
        if not await async_file_exists(file_path):
            logging.warning(f"File not found: {file_path}")
            return {"ok": False, "message": f"File not found: {file_path}", "data": None}

        # Get file type (run in thread pool if it's CPU intensive)
        loop = asyncio.get_event_loop()
        file_type, mime_type = await loop.run_in_executor(
            thread_pool,
            get_file_type,
            file_path
        )

        logging.info(f"Processing file: {file_path}, Type: {file_type}")

        if file_type == 'image':
            content = await process_image_async(file_path, mime_type, user_request)

        elif file_type == 'pdf':
            content = await process_pdf_async(file_path, user_request)
            if content is None:
                logging.warning("Failed to extract text from PDF")
                return {"ok": False, "message": "Failed to extract text from PDF", "data": None}

        elif file_type == 'excel':
            content = await process_excel_async(file_path, user_request)
            if content is None:
                logger.warning("Failed to extract data from Excel/CSV file")
                return {"ok": False, "message": "Failed to extract data from Excel/CSV file", "data": None}
        else:
            logger.warning(f"Unsupported file type: {file_type}")
            return {"ok": False, "message": f"Unsupported file type: {file_type}", "data": None}

        # Send async request to OpenAI
        response = await async_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a multilingual receipt and table data extraction assistant."
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=10000
        )

        result_str = response.choices[0].message.content

        if result_str == "###false###":
            logger.warning("This file/image doesn't have product data")
            return {"ok": False, "message": "This file/image doesn't have product data", "data": None}

        # Parse JSON in thread pool (if it's large and CPU intensive)
        loop = asyncio.get_event_loop()
        dict_data = await loop.run_in_executor(
            thread_pool,
            json.loads,
            result_str
        )

        return {"ok": True, "message": "success", "data": dict_data}

    except Exception as e:
        logger.error(f"Error: {e}")
        return {"ok": False, "message": f"Error: {e}", "data": None}


async def async_file_exists(file_path: str) -> bool:
    """Check if file exists asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, os.path.exists, file_path)


async def process_image_async(file_path: str, mime_type: str, user_request: Optional[str]) -> list:
    """Process image file asynchronously."""
    # Create prompt in thread pool
    loop = asyncio.get_event_loop()
    image_prompt = await loop.run_in_executor(
        thread_pool,
        create_prompt,
        'image',
        user_request
    )

    # Read file asynchronously
    async with aiofiles.open(file_path, "rb") as f:
        image_data = await f.read()
        encoded_image = base64.b64encode(image_data).decode('utf-8')

    return [
        {
            "type": "text",
            "text": image_prompt
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded_image}"
            }
        }
    ]


async def process_pdf_async(file_path: str, user_request: Optional[str]) -> Optional[list]:
    """Process PDF file asynchronously."""
    # Extract text in thread pool (CPU intensive)
    loop = asyncio.get_event_loop()
    extracted_text = await loop.run_in_executor(
        thread_pool,
        extract_text_from_pdf,
        file_path
    )

    if not extracted_text:
        return None

    # Create prompt in thread pool
    pdf_prompt = await loop.run_in_executor(
        thread_pool,
        create_prompt,
        'pdf',
        str({extracted_text[:15000]}),
        user_request
    )

    return [
        {
            "type": "text",
            "text": pdf_prompt
        }
    ]


async def process_excel_async(file_path: str, user_request: Optional[str]) -> Optional[list]:
    """Process Excel file asynchronously."""
    # Extract text in thread pool (CPU intensive)
    loop = asyncio.get_event_loop()
    extracted_text = await loop.run_in_executor(
        thread_pool,
        extract_text_from_excel,
        file_path
    )

    if not extracted_text:
        return None

    # Create prompt in thread pool
    excel_prompt = await loop.run_in_executor(
        thread_pool,
        create_prompt,
        'excel',
        extracted_text,
        user_request
    )

    return [
        {
            "type": "text",
            "text": excel_prompt
        }
    ]

async def process_file_background(file_path: str, user_request: Optional[str]):
    """Background processing function."""
    result = await convert_file_to_json_async(file_path, user_request)
    # Save result to core or send notification
    logger.info(f"Processing complete: {result}")

    # Cleanup
    if await async_file_exists(file_path):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(thread_pool, os.remove, file_path)


async def detect_excel_columns(excel_text: str, prompt: str = AI_PROMPT_EXCEL_COLUMN_MAPPING, model: str = "gpt-4o-mini") -> dict:
    """
    Uses OpenAI model to detect and map Excel columns from given text data.

    Args:
        prompt (str): Instruction text (AI_PROMPT_EXCEL_COLUMN_MAPPING).
        excel_text (str): Top rows of Excel formatted as plain text.
        model (str): OpenAI model name (default: gpt-4o-mini).

    Returns:
        dict: Parsed JSON result with columns, irrelevant_columns, irrelevant_rows.
    """

    # Combine instruction and Excel data
    user_prompt = f"{prompt}\n\nHere are the top rows from the Excel file:\n\n{excel_text}"

    try:
        response = await async_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a multilingual table structure detection assistant."},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=10000,
            response_format={"type": "json_object"}  # forces JSON output
        )

        result_text = response.choices[0].message.content.strip()

        try:
            result = json.loads(result_text)
            return {"ok": True, "result": result}

        except json.JSONDecodeError:
            logger.warning("⚠️ Warning: Model returned invalid JSON, returning raw text.")
            return {"ok": False, "error": result_text}

    except OpenAIError as e:
        logger.error(f"❌ OpenAI API error: {e}")
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return {"ok": False, "error": str(e)}

