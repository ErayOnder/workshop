"""
Orchestrates parallel Gemini image generation for a batch of 3 candidates.
Each candidate runs as an independent async task.
"""
import asyncio
import logging
from pathlib import Path

from ..db.database import AsyncSessionLocal
from ..crud.candidates import (
    set_candidate_generating,
    set_candidate_done,
    set_candidate_error,
    set_candidate_analysis_running,
    set_candidate_analysis_done,
    set_candidate_analysis_failed,
)
from ..generator import generate_one
from .image_analyzer import analyze_image
from .sse_bus import publish
from ..config import settings

logger = logging.getLogger(__name__)


async def _analyze_single(candidate_id: str, session_id: str, image_bytes: bytes) -> None:
    """Run image analysis and persist chips to DB. Failures are non-fatal."""
    try:
        async with AsyncSessionLocal() as db:
            await set_candidate_analysis_running(db, candidate_id)
            await db.commit()

        result = await analyze_image(image_bytes)
        if result is None:
            raise RuntimeError("analyze_image returned None")

        chip_dim_map = {
            chip["id"]: chip["dimensions"]
            for chip in result.get("like_chips", []) + result.get("dislike_chips", [])
        }

        async with AsyncSessionLocal() as db:
            await set_candidate_analysis_done(db, candidate_id, result, chip_dim_map)
            await db.commit()

        await publish(session_id, "analysis_done", {
            "candidate_id": candidate_id,
            "analysis_status": "done",
            "image_analysis": {
                "like_chips": result.get("like_chips", []),
                "dislike_chips": result.get("dislike_chips", []),
                "chip_dimension_map": chip_dim_map,
            },
        })

    except Exception as exc:
        logger.warning("Image analysis failed for candidate %s: %s", candidate_id, exc)
        try:
            async with AsyncSessionLocal() as db:
                await set_candidate_analysis_failed(db, candidate_id)
                await db.commit()
        except Exception:
            pass
        await publish(session_id, "analysis_done", {
            "candidate_id": candidate_id,
            "analysis_status": "failed",
            "image_analysis": None,
        })


async def _generate_single(
    candidate_id: str,
    session_id: str,
    product_image_bytes: bytes,
    mime: str,
    prompt: str,
) -> None:
    """Generate one image, persist result to DB, then run image analysis."""
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

        await publish(session_id, "candidate_done", {
            "candidate_id": candidate_id,
            "generation_status": "done",
            "image_url": f"/v1/images/{filename}",
            "error": None,
            "analysis_status": "pending",
        })

        # Analysis runs after image is marked done so the UI can display the image
        # immediately. Analysis results arrive ~1-2s later via SSE.
        await _analyze_single(candidate_id, session_id, image_bytes)

    except Exception as exc:
        async with AsyncSessionLocal() as db:
            await set_candidate_error(db, candidate_id, str(exc))
            await db.commit()
        await publish(session_id, "candidate_done", {
            "candidate_id": candidate_id,
            "generation_status": "error",
            "image_url": None,
            "error": str(exc),
            "analysis_status": "failed",
        })


async def generate_candidate_batch(
    candidate_ids: list[str],
    prompts: list[str],
    product_image_bytes: bytes,
    mime: str,
    session_id: str,
    round_number: int,
) -> None:
    """
    Fire 3 parallel Gemini image generation calls.
    candidate_ids and prompts must be aligned lists of length 3.
    Intended to run as a FastAPI background task.
    """
    tasks = [
        _generate_single(candidate_id, session_id, product_image_bytes, mime, prompt)
        for candidate_id, prompt in zip(candidate_ids, prompts)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    await publish(session_id, "round_complete", {
        "session_id": session_id,
        "round_number": round_number,
    })
