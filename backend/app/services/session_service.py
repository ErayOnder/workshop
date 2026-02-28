"""
Session orchestration: create, next-round, finalize.

Thin route handlers call into these functions. All business logic
and cross-module coordination lives here.
"""
import uuid
import logging
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..crud.users import ensure_user
from ..crud.products import create_product, get_product
from ..crud.sessions import (
    EMPTY_CONTEXT,
    create_session,
    get_session,
    increment_round,
    finalize_session,
    get_creative_context,
    save_creative_context,
)
from ..crud.candidates import get_candidates_for_round
from ..crud.feedback import get_feedback_candidate_ids_for_round
from ..core.feedback_processor import update_creative_context
from .generation_pipeline import run_round_pipeline

logger = logging.getLogger(__name__)


# ── Create session ──────────────────────────────────────────────────────── #

async def handle_create_session(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    image_bytes: bytes,
    mime: str,
    user_id: str,
    category: str | None,
) -> dict:
    """
    Create session + product + round 1, kick off pipeline in background.
    Returns immediately — candidates delivered via SSE.
    """
    if not user_id:
        user_id = str(uuid.uuid4())
    await ensure_user(db, user_id)

    product_filename = f"{uuid.uuid4()}.png"
    product_path = settings.uploads_dir / product_filename
    product_path.write_bytes(image_bytes)

    product = await create_product(db, user_id, category, product_filename)
    session = await create_session(db, user_id, product.id)
    round_number = await increment_round(db, session)

    context = dict(EMPTY_CONTEXT)
    await save_creative_context(db, session, context)
    await db.commit()

    background_tasks.add_task(
        run_round_pipeline,
        session.id, round_number, context, category,
        image_bytes, mime,
    )

    return {
        "session_id": session.id,
        "user_id": user_id,
        "round_number": round_number,
    }


# ── Next round ──────────────────────────────────────────────────────────── #

async def handle_next_round(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    session_id: str,
    force: bool,
) -> dict:
    """
    Advance round, kick off pipeline in background.
    Returns immediately — candidates delivered via SSE.
    """
    session = await get_session(db, session_id)
    if session is None:
        raise ValueError("Session not found")
    if session.status == "finalized":
        raise ValueError("Session is already finalized")

    current_candidates = await get_candidates_for_round(db, session_id, session.round_number)
    if not current_candidates:
        raise ValueError("No candidates in current round")

    if not force:
        candidate_ids = {c.id for c in current_candidates}
        reviewed_ids = await get_feedback_candidate_ids_for_round(db, session_id, candidate_ids)
        if not candidate_ids.issubset(reviewed_ids):
            raise ValueError("Feedback incomplete for current round")

    product = await get_product(db, session.product_id)
    if product is None:
        raise ValueError("Product not found")

    product_path = settings.uploads_dir / product.image_filename
    product_image_bytes = product_path.read_bytes()
    mime = _guess_mime(product.image_filename)

    # Update scene history from current round before advancing
    context = await get_creative_context(db, session_id)
    for c in current_candidates:
        if c.image_analysis and c.image_analysis.get("scene_description"):
            slot = (c.generation_config or {}).get("slot", "?")
            entry = f"Round {session.round_number}, {slot}: {c.image_analysis['scene_description']}"
            context = update_creative_context(context, [], [], [], None, entry)

    round_number = await increment_round(db, session)
    await save_creative_context(db, session, context)
    await db.commit()

    background_tasks.add_task(
        run_round_pipeline,
        session_id, round_number, context, product.category,
        product_image_bytes, mime,
    )

    return {"round_number": round_number}


# ── Finalize ────────────────────────────────────────────────────────────── #

async def handle_finalize(
    db: AsyncSession,
    session_id: str,
    selected_candidate_id: str,
) -> dict:
    """Finalize session, generate export crops."""
    from ..crud.candidates import get_candidate

    session = await get_session(db, session_id)
    if session is None:
        raise ValueError("Session not found")

    candidate = await get_candidate(db, selected_candidate_id)
    if candidate is None or candidate.session_id != session_id:
        raise ValueError("Candidate not found in this session")
    if candidate.image_filename is None:
        raise ValueError("Selected candidate image is not yet generated")

    hero_path = settings.outputs_dir / candidate.image_filename
    feed_filename, story_filename = _make_export_crops(hero_path, candidate.id)

    await finalize_session(db, session)
    await db.commit()

    return {
        "session_id": session_id,
        "hero_image_url": f"/v1/images/{candidate.image_filename}",
        "export_variants": {
            "feed_1x1": f"/v1/images/{feed_filename}",
            "story_9x16": f"/v1/images/{story_filename}",
        },
    }


# ── Helpers ─────────────────────────────────────────────────────────────── #

def _guess_mime(filename: str) -> str:
    if filename.endswith(".png"):
        return "image/png"
    if filename.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _make_export_crops(hero_path, candidate_id: str) -> tuple[str, str]:
    """Generate 1:1 and 9:16 export crops using Pillow."""
    from PIL import Image

    img = Image.open(hero_path).convert("RGB")
    w, h = img.size

    # 1:1 center crop -> 1080x1080
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    feed_img = img.crop((left, top, left + side, top + side)).resize((1080, 1080), Image.LANCZOS)
    feed_filename = f"{candidate_id}_feed.png"
    feed_img.save(settings.outputs_dir / feed_filename, "PNG", optimize=True)

    # 9:16 -> target 1080x1920
    target_w, target_h = 1080, 1920
    target_ratio = target_w / target_h
    src_ratio = w / h

    if src_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        story_img = img.crop((left, 0, left + new_w, h)).resize((target_w, target_h), Image.LANCZOS)
    else:
        new_h = int(w / target_ratio)
        if new_h <= h:
            top = (h - new_h) // 2
            story_img = img.crop((0, top, w, top + new_h)).resize((target_w, target_h), Image.LANCZOS)
        else:
            canvas = Image.new("RGB", (w, new_h), (255, 255, 255))
            y_offset = (new_h - h) // 2
            canvas.paste(img, (0, y_offset))
            story_img = canvas.resize((target_w, target_h), Image.LANCZOS)

    story_filename = f"{candidate_id}_story.png"
    story_img.save(settings.outputs_dir / story_filename, "PNG", optimize=True)

    return feed_filename, story_filename
