"""
Gemini vision analysis for generated images.
Produces image-specific like/dislike chips that map to preference dimensions.
"""
import json
import logging

from google import genai
from google.genai import types

from ..config import settings
from .dimensions import ALL_DIMENSIONS

logger = logging.getLogger(__name__)

_ALL_DIMS_STR = ", ".join(ALL_DIMENSIONS)

_ANALYSIS_PROMPT = f"""You are a jewelry photography critic analyzing a single AI-generated jewelry marketing photo.

Analyze what is visually notable in this image. Generate feedback chips that a user could tap to explain why they liked or disliked this specific image.

Return ONLY valid JSON matching this exact schema, no markdown, no extra text:
{{
  "like_chips": [
    {{"id": "<slug>", "label": "<2-5 word description>", "dimensions": ["<dim1>"]}}
  ],
  "dislike_chips": [
    {{"id": "<slug>", "label": "<2-5 word description>", "dimensions": ["<dim1>"]}}
  ]
}}

Rules:
- Generate 3 to 5 like_chips and 3 to 5 dislike_chips
- Each chip id must be lowercase with underscores only (e.g. warm_golden_glow)
- Each chip label must describe something visually specific to THIS image in 2-5 words
- Each chip dimensions list must contain 1 to 3 values from ONLY this list:
  {_ALL_DIMS_STR}
- like_chips: describe what works well (e.g. "Warm golden light flatters", "Ring sharp and centered")
- dislike_chips: describe what could be improved (e.g. "Background too cluttered", "Ring appears oversized", "Lighting too flat")
- Be specific to what you actually see — not generic observations"""


def _validate_chips(chips: list) -> list[dict]:
    """Validate and clean a list of chips. Strips invalid dimensions, caps at 5."""
    valid = []
    dim_set = set(ALL_DIMENSIONS)
    for chip in chips[:5]:
        if not isinstance(chip, dict):
            continue
        chip_id = chip.get("id", "")
        label = chip.get("label", "")
        dims = chip.get("dimensions", [])
        if not chip_id or not label:
            continue
        # Strip dimensions not in our vocabulary
        clean_dims = [d for d in dims if d in dim_set]
        if not clean_dims:
            continue
        valid.append({"id": chip_id, "label": label, "dimensions": clean_dims})
    return valid


async def analyze_image(image_bytes: bytes) -> dict | None:
    """
    Run Gemini vision analysis on a generated image.
    Returns {"like_chips": [...], "dislike_chips": [...]} or None on any failure.
    """
    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            types.Part.from_text(text=_ANALYSIS_PROMPT),
        ]

        response = await client.aio.models.generate_content(
            model=settings.gemini_analysis_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )

        if not response.candidates:
            logger.warning("Image analysis: Gemini returned no candidates")
            return None

        raw_text = ""
        for part in response.candidates[0].content.parts:
            if part.text:
                raw_text += part.text

        raw_text = raw_text.strip()
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        data = json.loads(raw_text)

        like_chips = _validate_chips(data.get("like_chips", []))
        dislike_chips = _validate_chips(data.get("dislike_chips", []))

        if len(like_chips) < 2 or len(dislike_chips) < 2:
            logger.warning(
                "Image analysis: insufficient chips after validation (like=%d, dislike=%d)",
                len(like_chips),
                len(dislike_chips),
            )
            return None

        return {"like_chips": like_chips, "dislike_chips": dislike_chips}

    except Exception as exc:
        logger.warning("Image analysis failed: %s", exc)
        return None
