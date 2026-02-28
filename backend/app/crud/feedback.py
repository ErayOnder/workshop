import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import FeedbackEvent

logger = logging.getLogger(__name__)


async def create_or_update_feedback_event(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    candidate_id: str,
    action: str,
    reason_tags: list[str],
    text_note: str | None,
    reward: float,
) -> FeedbackEvent:
    result = await db.execute(
        select(FeedbackEvent).where(
            FeedbackEvent.session_id == session_id,
            FeedbackEvent.candidate_id == candidate_id,
            FeedbackEvent.action == action,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        logger.info("feedback_event_created session=%s candidate=%s action=%s", session_id, candidate_id, action)
        event = FeedbackEvent(
            session_id=session_id,
            user_id=user_id,
            candidate_id=candidate_id,
            action=action,
            reason_tags=reason_tags,
            text_note=text_note,
            reward=reward,
        )
        db.add(event)
    else:
        logger.info("feedback_event_updated session=%s candidate=%s action=%s (was %s)", session_id, candidate_id, action, event.action)
        event.action = action
        event.reason_tags = reason_tags
        event.text_note = text_note
        event.reward = reward

    await db.flush()
    return event


async def get_feedback_candidate_ids_for_round(
    db: AsyncSession, session_id: str, candidate_ids: set[str]
) -> set[str]:
    """Return the subset of candidate_ids that have at least one feedback event."""
    result = await db.execute(
        select(FeedbackEvent.candidate_id).where(
            FeedbackEvent.session_id == session_id,
            FeedbackEvent.candidate_id.in_(candidate_ids),
        )
    )
    return set(result.scalars().all())
