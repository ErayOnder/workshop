"""
Feedback orchestration: process user feedback and update creative context.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.sessions import get_session, get_creative_context, save_creative_context
from ..crud.candidates import get_candidate
from ..crud.feedback import create_or_update_feedback_event
from ..core.feedback_processor import extract_corrections_and_updates, update_creative_context

logger = logging.getLogger(__name__)

_REWARD_MAP = {"like": 1.0, "dislike": -1.0, "save": 4.0}


async def handle_feedback(
    db: AsyncSession,
    session_id: str,
    candidate_id: str,
    action: str,
    reason_tags: list[str],
    text_note: str | None,
) -> dict:
    """Process feedback, update creative context, persist event. Returns reward."""
    session = await get_session(db, session_id)
    if session is None:
        raise ValueError("Session not found")
    if session.status == "finalized":
        raise ValueError("Session is already finalized")

    candidate = await get_candidate(db, candidate_id)
    if candidate is None or candidate.session_id != session_id:
        raise ValueError("Candidate not found in this session")

    reward = _REWARD_MAP.get(action, 0.0)

    logger.info(
        "feedback session=%s candidate=%s action=%s tags=%s reward=%.2f",
        session_id, candidate_id, action, reason_tags, reward,
    )

    aesthetic_tags = (candidate.generation_config or {}).get("aesthetic_tags", [])
    updates = extract_corrections_and_updates(
        action=action,
        reason_tags=reason_tags,
        text_note=text_note,
        candidate_image_analysis=candidate.image_analysis,
        candidate_aesthetic_tags=aesthetic_tags,
    )

    context = await get_creative_context(db, session_id)
    new_context = update_creative_context(
        context,
        new_corrections=updates["corrections"],
        liked_tags=updates["liked_tags"],
        disliked_tags=updates["disliked_tags"],
        structural_update=updates["structural_update"],
        scene_to_add_to_history=None,
    )
    await save_creative_context(db, session, new_context)

    await create_or_update_feedback_event(
        db,
        session_id=session_id,
        user_id=session.user_id,
        candidate_id=candidate_id,
        action=action,
        reason_tags=reason_tags,
        text_note=text_note,
        reward=reward,
    )
    await db.commit()

    return {"feedback_accepted": True, "reward": reward}
