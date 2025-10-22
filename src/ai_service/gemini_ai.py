import asyncio
import json
import logging
import os
import google.generativeai as genai
from PIL import Image
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from src.core.conf import GEMINI_API_KEY
from src.ai_service.prompt import create_gemini_prompt

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
            prompt = create_gemini_prompt(prompt_type="pdf")
            result = await asyncio.to_thread(_extract_from_pdf, file_path, prompt)
        elif ext in image_formats:
            prompt = create_gemini_prompt(prompt_type="img")
            # Process Image
            result = await asyncio.to_thread(_extract_from_image, file_path, prompt)
        else:
            err_msg = f"Unsupported file format: {ext}. Supported formats: PDF, {', '.join(image_formats)}"
            logger.error(err_msg)
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=err_msg
            )

        if result == "###false###":
            err_msg = "Ai model couldn't process image data."
            logger.error(err_msg)
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=err_msg
            )
        result = result.replace("```json", "")
        result = result.replace("```", "")
        try:
            json_data = json.loads(result)
        except Exception as e:
            err_msg = f"Failed to parse json data: {e}"
            logger.error(err_msg)
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=err_msg
            )
        else:
            return {"ok": True, "message": "success", "data": json_data}

    except Exception as e:
        err_msg = f"Error processing file {file_path}: {str(e)}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=err_msg
        )


def _extract_from_image(image_path: str, prompt: str) -> str:
    """Helper function to extract data from image"""
    img = Image.open(image_path)
    response = model.generate_content([prompt, img])
    return response.text


def _extract_from_pdf(pdf_path: str, prompt: str) -> str:
    """Helper function to extract data from PDF"""
    pdf_file = genai.upload_file(pdf_path)
    response = model.generate_content([prompt, pdf_file])
    genai.delete_file(pdf_file.name)
    return response.text

