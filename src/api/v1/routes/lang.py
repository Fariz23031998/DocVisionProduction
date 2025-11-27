import logging
from fastapi import APIRouter

from src.translations.translator_service import Translator

logger = logging.getLogger("DocVision")
router = APIRouter(prefix="/lang", tags=["Languages"])

translator = Translator()

@router.get("/{lang_code}")
async def get_language(lang_code: str):
    if lang_code.lower() not in ("en", "ru", "uz", "tj"):
        lang_code = "en"

    return translator.get_language_translations(lang_code)

@router.get("/{lang_code}/version")
async def get_version(lang_code: str):
    if lang_code.lower() not in ("en", "ru", "uz", "tj"):
        lang_code = "en"

    return translator.get_language_version(lang_code)
