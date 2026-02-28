from google import genai
from google.genai import types
from ..config import settings


async def generate_one(image_bytes: bytes, mime: str, prompt: str) -> bytes:
    """Call Gemini to generate a single image from a reference image + prompt."""
    client = genai.Client(api_key=settings.gemini_api_key)

    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime),
        types.Part.from_text(text=prompt),
    ]

    response = await client.aio.models.generate_content(
        model=settings.gemini_image_model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates")

    text_parts = []
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            return part.inline_data.data
        if part.text:
            text_parts.append(part.text)

    raise RuntimeError(
        f"Gemini returned no image. Text: {' '.join(text_parts)[:200]}"
    )
