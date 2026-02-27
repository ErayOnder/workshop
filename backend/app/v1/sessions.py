import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
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
    get_creative_context,
    save_creative_context,
)
from ..crud.candidates import (
    create_candidate,
    get_candidate,
    get_candidates_for_round,
)
from ..crud.feedback import create_or_update_feedback_event
from ..core.creative_director import generate_scene_briefs
from ..core.feedback_processor import extract_corrections_and_updates, update_creative_context
from ..core.candidate_generator import generate_candidate_batch
from ..core.sse_bus import subscribe, unsubscribe

router = APIRouter(tags=["sessions"])
logger = logging.getLogger(__name__)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}

_EMPTY_CONTEXT: dict = {
    "structural": {},
    "corrections": [],
    "scene_history": [],
    "liked_tags": [],
    "disliked_tags": [],
}

_REWARD_MAP = {"like": 1.0, "dislike": -1.0, "save": 4.0}


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
    if image.content_type not in ALLOWED_MIMES:
        raise HTTPException(400, f"Unsupported image type: {image.content_type}")

    image_bytes = await image.read()
    mime = image.content_type

    if not user_id:
        user_id = str(uuid.uuid4())
    await ensure_user(db, user_id)

    product_filename = f"{uuid.uuid4()}.png"
    product_path = settings.uploads_dir / product_filename
    product_path.write_bytes(image_bytes)

    product = await create_product(db, user_id, category or None, product_filename)
    session = await create_session(db, user_id, product.id)

    round_number = await increment_round(db, session)

    # Generate 3 creative scene briefs via LLM
    context = dict(_EMPTY_CONTEXT)
    scenes = await generate_scene_briefs(context, category or None, round_number)
    await save_creative_context(db, session, context)

    candidates: list[Candidate] = []
    for scene in scenes:
        c = await create_candidate(
            db,
            session.id,
            round_number,
            generation_config={
                "scene_title": scene["scene_title"],
                "aesthetic_tags": scene["aesthetic_tags"],
                "slot": scene["slot"],
                "fields": scene["fields"],
            },
            rendered_prompt=scene["scene_brief"],
        )
        candidates.append(c)

    await db.commit()

    prompts = [s["scene_brief"] for s in scenes]
    candidate_ids = [c.id for c in candidates]
    background_tasks.add_task(
        generate_candidate_batch, candidate_ids, prompts, image_bytes, mime,
        session.id, round_number,
    )

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
# GET /v1/sessions/{session_id}/events — SSE stream for generation status     #
# --------------------------------------------------------------------------- #

@router.get("/sessions/{session_id}/events")
async def candidate_events(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    candidates = await get_candidates_for_round(db, session_id, session.round_number)

    async def event_stream():
        q = subscribe(session_id)
        try:
            all_settled = True
            for c in candidates:
                if c.generation_status in ("done", "error"):
                    yield _sse("candidate_done", {
                        "candidate_id": c.id,
                        "generation_status": c.generation_status,
                        "image_url": _candidate_url(c.image_filename) if c.image_filename else None,
                        "error": c.generation_error,
                        "analysis_status": c.analysis_status,
                    })
                else:
                    all_settled = False

                if c.analysis_status in ("done", "failed"):
                    analysis = None
                    if c.image_analysis and c.chip_dimension_map:
                        chip_dim_map = {
                            chip["id"]: chip["dimensions"]
                            for chip in c.image_analysis.get("like_chips", []) + c.image_analysis.get("dislike_chips", [])
                        }
                        analysis = {
                            "like_chips": c.image_analysis.get("like_chips", []),
                            "dislike_chips": c.image_analysis.get("dislike_chips", []),
                            "chip_dimension_map": chip_dim_map,
                        }
                    yield _sse("analysis_done", {
                        "candidate_id": c.id,
                        "analysis_status": c.analysis_status,
                        "image_analysis": analysis,
                    })
                elif c.generation_status not in ("done", "error"):
                    all_settled = False

            if all_settled:
                yield _sse("round_complete", {
                    "session_id": session_id,
                    "round_number": session.round_number,
                })
                return

            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                yield _sse(msg["event"], msg["data"])
                if msg["event"] == "round_complete":
                    break

        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(session_id, q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# --------------------------------------------------------------------------- #
# POST /v1/sessions/{session_id}/feedback — submit feedback only              #
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

    reward = _REWARD_MAP.get(body.action, 0.0)
    logger.info(
        "feedback_received session=%s candidate=%s action=%s reason_tags=%s text_note=%s reward=%.2f",
        session_id, body.candidate_id, body.action, body.reason_tags, body.text_note, reward,
    )

    # Extract corrections and aesthetic updates from feedback
    aesthetic_tags = (candidate.generation_config or {}).get("aesthetic_tags", [])
    updates = extract_corrections_and_updates(
        action=body.action,
        reason_tags=body.reason_tags,
        text_note=body.text_note,
        candidate_image_analysis=candidate.image_analysis,
        candidate_aesthetic_tags=aesthetic_tags,
    )

    # Merge into session creative context
    context = await get_creative_context(db, session_id)
    new_context = update_creative_context(
        context,
        new_corrections=updates["corrections"],
        liked_tags=updates["liked_tags"],
        disliked_tags=updates["disliked_tags"],
        structural_update=updates["structural_update"],
        scene_to_add_to_history=None,  # history added in next-round
    )
    await save_creative_context(db, session, new_context)

    await create_or_update_feedback_event(
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

    return FeedbackResponse(feedback_accepted=True, reward=reward)


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

    # Load product for image bytes + category
    from sqlalchemy import select as sa_select
    from ..db.models import Product
    product_result = await db.execute(sa_select(Product).where(Product.id == session.product_id))
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(500, "Product image not found")

    product_path = settings.uploads_dir / product.image_filename
    product_image_bytes = product_path.read_bytes()
    mime = _guess_mime(product.image_filename)

    # Add scene descriptions from current round to history before advancing
    context = await get_creative_context(db, session_id)
    for c in current_candidates:
        if c.image_analysis and c.image_analysis.get("scene_description"):
            slot = (c.generation_config or {}).get("slot", "?")
            entry = f"Round {session.round_number}, {slot}: {c.image_analysis['scene_description']}"
            context = update_creative_context(context, [], [], [], None, entry)

    # Advance round
    round_number = await increment_round(db, session)

    # Generate 3 new scene briefs
    scenes = await generate_scene_briefs(context, product.category, round_number)
    await save_creative_context(db, session, context)

    next_candidates: list[Candidate] = []
    for scene in scenes:
        c = await create_candidate(
            db,
            session_id,
            round_number,
            generation_config={
                "scene_title": scene["scene_title"],
                "aesthetic_tags": scene["aesthetic_tags"],
                "slot": scene["slot"],
                "fields": scene["fields"],
            },
            rendered_prompt=scene["scene_brief"],
        )
        next_candidates.append(c)

    await db.commit()

    prompts = [s["scene_brief"] for s in scenes]
    next_ids = [c.id for c in next_candidates]
    background_tasks.add_task(
        generate_candidate_batch, next_ids, prompts, product_image_bytes, mime,
        session_id, round_number,
    )

    return NextRoundResponse(
        advanced=True,
        round_number=round_number,
        next_candidates=[_candidate_to_out(c) for c in next_candidates],
    )


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

    hero_path = settings.outputs_dir / candidate.image_filename
    feed_filename, story_filename = _make_export_crops(hero_path, candidate.id)

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
