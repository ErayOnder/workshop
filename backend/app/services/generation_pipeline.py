"""
Background pipeline: scene briefs -> candidate DB records -> SSE -> image gen -> analysis.

Runs entirely as a background task with its own DB sessions.
"""
import asyncio
import logging
from pathlib import Path

from ..db.database import AsyncSessionLocal
from ..crud.candidates import (
    create_candidate,
    set_candidate_generating,
    set_candidate_done,
    set_candidate_error,
    set_candidate_analysis_running,
    set_candidate_analysis_done,
    set_candidate_analysis_failed,
)
from ..crud.sessions import get_session, save_creative_context
from ..core.creative_director import generate_scene_briefs
from ..core.image_generator import generate_one
from ..core.image_analyzer import analyze_image
from ..core.sse_bus import publish
from ..config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full round pipeline (scene briefs + candidate creation + image gen)
# ---------------------------------------------------------------------------

async def run_round_pipeline(
    session_id: str,
    round_number: int,
    creative_context: dict,
    category: str | None,
    product_image_bytes: bytes,
    mime: str,
) -> None:
    """
    Complete background pipeline for a round:
    1. Generate scene briefs (LLM text call)
    2. Create candidate DB records
    3. Publish candidates_created SSE event
    4. Run parallel image generation + analysis
    5. Publish round_complete SSE event
    """
    try:
        scenes = await generate_scene_briefs(creative_context, category, round_number)

        async with AsyncSessionLocal() as db:
            session = await get_session(db, session_id)
            if session is None:
                logger.error("Pipeline: session %s not found", session_id)
                return
            await save_creative_context(db, session, creative_context)

            candidate_ids: list[str] = []
            prompts: list[str] = []
            candidates_out: list[dict] = []
            for scene in scenes:
                c = await create_candidate(
                    db, session_id, round_number,
                    generation_config={
                        "scene_title": scene["scene_title"],
                        "aesthetic_tags": scene["aesthetic_tags"],
                        "slot": scene["slot"],
                        "fields": scene["fields"],
                    },
                    rendered_prompt=scene["scene_brief"],
                )
                candidate_ids.append(c.id)
                prompts.append(scene["scene_brief"])
                candidates_out.append({
                    "candidate_id": c.id,
                    "generation_status": "pending",
                    "image_url": None,
                    "error": None,
                    "analysis_status": "pending",
                    "image_analysis": None,
                })
            await db.commit()

        await publish(session_id, "candidates_created", {
            "session_id": session_id,
            "round_number": round_number,
            "candidates": candidates_out,
        })

        await _run_image_generation(candidate_ids, prompts, product_image_bytes, mime, session_id)

    except Exception as exc:
        logger.error("Pipeline failed session=%s round=%d: %s", session_id, round_number, exc)
        await publish(session_id, "pipeline_error", {
            "session_id": session_id,
            "round_number": round_number,
            "error": str(exc),
        })
        return

    await publish(session_id, "round_complete", {
        "session_id": session_id,
        "round_number": round_number,
    })


# ---------------------------------------------------------------------------
# Image generation batch (used by run_round_pipeline)
# ---------------------------------------------------------------------------

async def _run_image_generation(
    candidate_ids: list[str],
    prompts: list[str],
    product_image_bytes: bytes,
    mime: str,
    session_id: str,
) -> None:
    """Fire parallel Gemini image generation calls."""
    tasks = [
        _generate_single(cid, session_id, product_image_bytes, mime, prompt)
        for cid, prompt in zip(candidate_ids, prompts)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# Single candidate: generate image -> analyze
# ---------------------------------------------------------------------------

async def _generate_single(
    candidate_id: str,
    session_id: str,
    product_image_bytes: bytes,
    mime: str,
    prompt: str,
) -> None:
    """Generate one image, persist to DB, then run analysis."""
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
