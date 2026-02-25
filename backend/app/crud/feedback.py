from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import FeedbackEvent


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
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
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
        event.action = action
        event.reason_tags = reason_tags
        event.text_note = text_note
        event.reward = reward

    await db.flush()
    return event
