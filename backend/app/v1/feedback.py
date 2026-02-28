from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..schemas.feedback import FeedbackRequest, FeedbackResponse
from ..services import feedback_service

router = APIRouter(tags=["feedback"])


@router.post("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    session_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await feedback_service.handle_feedback(
            db,
            session_id=session_id,
            candidate_id=body.candidate_id,
            action=body.action,
            reason_tags=body.reason_tags,
            text_note=body.text_note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return FeedbackResponse(**result)
