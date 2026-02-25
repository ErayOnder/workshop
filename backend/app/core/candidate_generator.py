"""
Orchestrates parallel Gemini image generation for a batch of 3 candidates.
Each candidate runs as an independent async task.
"""
import asyncio
import uuid
from pathlib import Path

from ..db.database import AsyncSessionLocal
from ..crud.candidates import set_candidate_generating, set_candidate_done, set_candidate_error
from ..generator import generate_one
from ..config import settings


async def _generate_single(
    candidate_id: str,
    product_image_bytes: bytes,
    mime: str,
    prompt: str,
) -> None:
    """Generate one image and persist the result to DB."""
    async with AsyncSessionLocal() as db:
        await set_candidate_generating(db, candidate_id)
        await db.commit()

    try:
        image_bytes = await generate_one(product_image_bytes, mime, prompt)
        filename = f"{candidate_id}.png"
        output_path: Path = settings.outputs_dir / filename
        output_path.write_bytes(image_bytes)

        async with AsyncSessionLocal() as db:
            await set_candidate_done(db, candidate_id, filename)
            await db.commit()

    except Exception as exc:
        async with AsyncSessionLocal() as db:
            await set_candidate_error(db, candidate_id, str(exc))
            await db.commit()


async def generate_candidate_batch(
    candidate_ids: list[str],
    prompts: list[str],
    product_image_bytes: bytes,
    mime: str,
) -> None:
    """
    Fire 3 parallel Gemini image generation calls.
    candidate_ids and prompts must be aligned lists of length 3.
    Intended to run as a FastAPI background task.
    """
    tasks = [
        _generate_single(candidate_id, product_image_bytes, mime, prompt)
        for candidate_id, prompt in zip(candidate_ids, prompts)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
