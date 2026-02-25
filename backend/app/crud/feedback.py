from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import FeedbackEvent


async def create_feedback_event(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    candidate_id: str,
    action: str,
    reason_tags: list[str],
    text_note: str | None,
    reward: float,
) -> FeedbackEvent:
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
    await db.flush()
    return event
