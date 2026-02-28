import asyncio
import logging

from google import genai
from google.genai import types
from ..config import settings

logger = logging.getLogger(__name__)

IMAGE_GEN_TIMEOUT = 120  # seconds


async def generate_one(image_bytes: bytes, mime: str, prompt: str) -> bytes:
    """Call Gemini to generate a single image from a reference image + prompt."""
    client = genai.Client(api_key=settings.gemini_api_key)

    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime),
        types.Part.from_text(text=prompt),
    ]

    logger.info("image_generator: calling model=%s", settings.gemini_image_model)
    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=settings.gemini_image_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            ),
            timeout=IMAGE_GEN_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error("image_generator: timed out after %ds", IMAGE_GEN_TIMEOUT)
        raise RuntimeError(f"Gemini image generation timed out after {IMAGE_GEN_TIMEOUT}s")

    if not response.candidates:
        logger.error("image_generator: Gemini returned no candidates")
        raise RuntimeError("Gemini returned no candidates")

    text_parts = []
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            logger.info("image_generator: got image (%d bytes)", len(part.inline_data.data))
            return part.inline_data.data
        if part.text:
            text_parts.append(part.text)

    msg = f"Gemini returned no image. Text: {' '.join(text_parts)[:200]}"
    logger.error("image_generator: %s", msg)
    raise RuntimeError(msg)
