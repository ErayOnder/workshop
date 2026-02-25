import logging
import uuid
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..db.models import Candidate
from ..config import settings
from ..schemas import (
    CandidateOut,
    CandidatesResponse,
    CreateSessionResponse,
    FeedbackRequest,
    FeedbackResponse,
    ImageAnalysisData,
    NextRoundRequest,
    NextRoundResponse,
    FinalizeRequest,
    FinalizeResponse,
)
from ..crud.sessions import (
    ensure_user,
    create_product,
    create_session,
    get_session,
    increment_round,
    finalize_session,
)
from ..crud.candidates import (
    create_candidate,
    get_candidate,
    get_candidates_for_round,
)
from ..crud.feedback import create_or_update_feedback_event
from ..crud.profiles import (
    get_or_create_profile,
    get_dimensions,
    upsert_dimension,
    increment_profile_interactions,
)
from ..core.prompt_agent import generate_three_configs, compile_prompt
from ..core.preference_engine import (
    compute_reward,
    update_profile_from_feedback,
    blend_session_into_longterm,
    should_exploit,
)
from ..core.candidate_generator import generate_candidate_batch

router = APIRouter(tags=["sessions"])
logger = logging.getLogger(__name__)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}


def _candidate_url(filename: str) -> str:
    return f"/v1/images/{filename}"


def _candidate_to_out(c: Candidate) -> CandidateOut:
    analysis: ImageAnalysisData | None = None
    if c.image_analysis and c.chip_dimension_map:
        analysis = ImageAnalysisData(
            like_chips=c.image_analysis.get("like_chips", []),
            dislike_chips=c.image_analysis.get("dislike_chips", []),
            chip_dimension_map=c.chip_dimension_map,
        )
    return CandidateOut(
        candidate_id=c.id,
        generation_status=c.generation_status,  # type: ignore[arg-type]
        image_url=_candidate_url(c.image_filename) if c.image_filename else None,
        error=c.generation_error,
        analysis_status=c.analysis_status,  # type: ignore[arg-type]
        image_analysis=analysis,
    )


# --------------------------------------------------------------------------- #
# POST /v1/sessions — create session + kick off first round                   #
# --------------------------------------------------------------------------- #

@router.post("/sessions", response_model=CreateSessionResponse, status_code=202)
async def create_new_session(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    image: UploadFile = File(...),
    user_id: str = Form(default=""),
    category: str = Form(default=""),
):
    # Validate image
    if image.content_type not in ALLOWED_MIMES:
        raise HTTPException(400, f"Unsupported image type: {image.content_type}")

    image_bytes = await image.read()
    mime = image.content_type

    # Resolve user (create anonymous if needed)
    if not user_id:
        user_id = str(uuid.uuid4())
    await ensure_user(db, user_id)

    # Save product image
    product_filename = f"{uuid.uuid4()}.png"
    product_path = settings.uploads_dir / product_filename
    product_path.write_bytes(image_bytes)

    # Create product + session
    product = await create_product(db, user_id, category or None, product_filename)
    session = await create_session(db, user_id, product.id)

    # Advance to round 1
    round_number = await increment_round(db, session)

    # Load preference profile
    profile = await get_or_create_profile(db, user_id)
    dim_map = await get_dimensions(db, profile.id)
    profile_scores = {name: dim.score for name, dim in dim_map.items()}

    # Generate 3 configs + prompts
    configs = generate_three_configs(profile_scores, round_number, category or None)
    prompts = [compile_prompt(c) for c in configs]

    # Create candidate rows
    candidates: list[Candidate] = []
    for config, prompt in zip(configs, prompts):
        c = await create_candidate(db, session.id, round_number, config, prompt)
        candidates.append(c)

    await db.commit()

    # Fire generation in background
    candidate_ids = [c.id for c in candidates]
    background_tasks.add_task(generate_candidate_batch, candidate_ids, prompts, image_bytes, mime)

    return CreateSessionResponse(
        session_id=session.id,
        user_id=user_id,
        round_number=round_number,
        candidates=[_candidate_to_out(c) for c in candidates],
    )


# --------------------------------------------------------------------------- #
# GET /v1/sessions/{session_id}/candidates — poll generation status           #
# --------------------------------------------------------------------------- #

@router.get("/sessions/{session_id}/candidates", response_model=CandidatesResponse)
async def poll_candidates(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    candidates = await get_candidates_for_round(db, session_id, session.round_number)
    return CandidatesResponse(
        session_id=session_id,
        round_number=session.round_number,
        candidates=[_candidate_to_out(c) for c in candidates],
    )


# --------------------------------------------------------------------------- #
# POST /v1/sessions/{session_id}/feedback — submit feedback only               #
# --------------------------------------------------------------------------- #

@router.post("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    session_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    if session.status == "finalized":
        raise HTTPException(400, "Session is already finalized")

    candidate = await get_candidate(db, body.candidate_id)
    if candidate is None or candidate.session_id != session_id:
        raise HTTPException(404, "Candidate not found in this session")

    logger.info(
        "feedback_received session=%s candidate=%s action=%s reason_tags=%s text_note=%s",
        session_id, body.candidate_id, body.action, body.reason_tags, body.text_note,
    )

    # Get current profile
    profile = await get_or_create_profile(db, session.user_id)
    dim_map = await get_dimensions(db, profile.id)
    profile_scores = {n: d.score for n, d in dim_map.items()}
    profile_confs = {n: d.confidence for n, d in dim_map.items()}
    profile_counts = {n: d.interaction_count for n, d in dim_map.items()}

    # Compute reward and update profile
    reward = compute_reward(body.action)
    logger.info("feedback_reward session=%s action=%s reward=%.2f", session_id, body.action, reward)

    new_scores, new_confs, new_counts = update_profile_from_feedback(
        profile_scores,
        profile_confs,
        profile_counts,
        candidate.generation_config,
        body.action,
        body.reason_tags,
        body.chip_dimension_map or None,
    )

    # Persist updated dimensions
    for dim_name in new_scores:
        await upsert_dimension(
            db,
            profile.id,
            dim_name,
            new_scores[dim_name],
            new_confs[dim_name],
            new_counts[dim_name],
        )
    await increment_profile_interactions(db, profile)

    # Store feedback event (upsert by candidate so edits overwrite prior choice)
    event = await create_or_update_feedback_event(
        db,
        session_id=session_id,
        user_id=session.user_id,
        candidate_id=body.candidate_id,
        action=body.action,
        reason_tags=body.reason_tags,
        text_note=body.text_note,
        reward=reward,
    )

    await db.commit()

    logger.info("feedback_saved session=%s candidate=%s event_id=%s", session_id, body.candidate_id, event.id)

    return FeedbackResponse(
        feedback_accepted=True,
        reward=reward,
    )


# --------------------------------------------------------------------------- #
# POST /v1/sessions/{session_id}/next-round — generate next round candidates  #
# --------------------------------------------------------------------------- #

@router.post("/sessions/{session_id}/next-round", response_model=NextRoundResponse)
async def next_round(
    session_id: str,
    body: NextRoundRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    if session.status == "finalized":
        raise HTTPException(400, "Session is already finalized")

    current_candidates = await get_candidates_for_round(db, session_id, session.round_number)
    if not current_candidates:
        raise HTTPException(400, "No candidates in current round")

    if not body.force and not await _is_round_feedback_complete(db, session_id, session.round_number):
        raise HTTPException(409, "Feedback incomplete for current round")

    # Get latest profile state for next-round proposal
    profile = await get_or_create_profile(db, session.user_id)
    dim_map = await get_dimensions(db, profile.id)
    profile_scores = {n: d.score for n, d in dim_map.items()}

    # Determine exploit mode (consecutive_likes not used in V1)
    save_pressed = await _save_exists_for_round(db, session_id, session.round_number)
    exploit = should_exploit(session.round_number, save_pressed, 0)

    # Advance to next round
    round_number = await increment_round(db, session)

    # Load product image for next generation
    from sqlalchemy import select as sa_select
    from ..db.models import Product
    product_result = await db.execute(sa_select(Product).where(Product.id == session.product_id))
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(500, "Product image not found")

    product_path = settings.uploads_dir / product.image_filename
    product_image_bytes = product_path.read_bytes()
    mime = _guess_mime(product.image_filename)

    # Generate next 3 configs + prompts
    configs = generate_three_configs(profile_scores, round_number, None, exploit_mode=exploit)
    prompts = [compile_prompt(c) for c in configs]

    # Create candidate rows for next round
    next_candidates: list[Candidate] = []
    for config, prompt in zip(configs, prompts):
        c = await create_candidate(db, session_id, round_number, config, prompt)
        next_candidates.append(c)

    await db.commit()

    # Fire generation in background
    next_ids = [c.id for c in next_candidates]
    background_tasks.add_task(generate_candidate_batch, next_ids, prompts, product_image_bytes, mime)

    return NextRoundResponse(
        advanced=True,
        round_number=round_number,
        next_candidates=[_candidate_to_out(c) for c in next_candidates],
    )


def _count_consecutive_likes(session_id: str, db: AsyncSession) -> int:
    # Simplified — in V1 we just return 0; proper counting requires session history
    return 0


async def _is_round_feedback_complete(db: AsyncSession, session_id: str, round_number: int) -> bool:
    from sqlalchemy import select as sa_select
    from ..db.models import FeedbackEvent

    round_candidates = await get_candidates_for_round(db, session_id, round_number)
    if not round_candidates:
        return False

    candidate_ids = {c.id for c in round_candidates}
    feedback_result = await db.execute(
        sa_select(FeedbackEvent.candidate_id).where(
            FeedbackEvent.session_id == session_id,
            FeedbackEvent.candidate_id.in_(candidate_ids),
        )
    )
    reviewed_ids = set(feedback_result.scalars().all())
    return candidate_ids.issubset(reviewed_ids)


async def _save_exists_for_round(db: AsyncSession, session_id: str, round_number: int) -> bool:
    from sqlalchemy import select as sa_select
    from ..db.models import FeedbackEvent

    round_candidates = await get_candidates_for_round(db, session_id, round_number)
    if not round_candidates:
        return False
    candidate_ids = {c.id for c in round_candidates}

    result = await db.execute(
        sa_select(FeedbackEvent.id).where(
            FeedbackEvent.session_id == session_id,
            FeedbackEvent.action == "save",
            FeedbackEvent.candidate_id.in_(candidate_ids),
        )
    )
    return result.scalar_one_or_none() is not None


def _guess_mime(filename: str) -> str:
    if filename.endswith(".png"):
        return "image/png"
    if filename.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


# --------------------------------------------------------------------------- #
# POST /v1/sessions/{session_id}/finalize                                     #
# --------------------------------------------------------------------------- #

@router.post("/sessions/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize(
    session_id: str,
    body: FinalizeRequest,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    candidate = await get_candidate(db, body.selected_candidate_id)
    if candidate is None or candidate.session_id != session_id:
        raise HTTPException(404, "Candidate not found in this session")
    if candidate.image_filename is None:
        raise HTTPException(400, "Selected candidate image is not yet generated")

    # Generate export crops
    hero_path = settings.outputs_dir / candidate.image_filename
    feed_filename, story_filename = _make_export_crops(hero_path, candidate.id)

    # Finalize session
    await finalize_session(db, session)
    await db.commit()

    return FinalizeResponse(
        session_id=session_id,
        hero_image_url=_candidate_url(candidate.image_filename),
        export_variants={
            "feed_1x1": _candidate_url(feed_filename),
            "story_9x16": _candidate_url(story_filename),
        },
    )


def _make_export_crops(hero_path, candidate_id: str) -> tuple[str, str]:
    """Generate 1:1 and 9:16 export crops using Pillow."""
    from PIL import Image

    img = Image.open(hero_path).convert("RGB")
    w, h = img.size

    # 1:1 center crop → 1080×1080
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    feed_img = img.crop((left, top, left + side, top + side)).resize((1080, 1080), Image.LANCZOS)
    feed_filename = f"{candidate_id}_feed.png"
    feed_img.save(settings.outputs_dir / feed_filename, "PNG", optimize=True)

    # 9:16 → target 1080×1920
    target_w, target_h = 1080, 1920
    target_ratio = target_w / target_h
    src_ratio = w / h

    if src_ratio > target_ratio:
        # Image is wider than 9:16 → crop width
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        story_img = img.crop((left, 0, left + new_w, h)).resize((target_w, target_h), Image.LANCZOS)
    else:
        # Image is taller or narrower → pad top/bottom with white
        new_h = int(w / target_ratio)
        if new_h <= h:
            top = (h - new_h) // 2
            story_img = img.crop((0, top, w, top + new_h)).resize((target_w, target_h), Image.LANCZOS)
        else:
            # Pad with white
            canvas = Image.new("RGB", (w, new_h), (255, 255, 255))
            y_offset = (new_h - h) // 2
            canvas.paste(img, (0, y_offset))
            story_img = canvas.resize((target_w, target_h), Image.LANCZOS)

    story_filename = f"{candidate_id}_story.png"
    story_img.save(settings.outputs_dir / story_filename, "PNG", optimize=True)

    return feed_filename, story_filename
