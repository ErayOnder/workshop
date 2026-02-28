import logging
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..schemas.sessions import (
    CreateSessionResponse,
    NextRoundRequest,
    NextRoundResponse,
    FinalizeRequest,
    FinalizeResponse,
)
from ..services import session_service

router = APIRouter(tags=["sessions"])
logger = logging.getLogger(__name__)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}


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
    result = await session_service.handle_create_session(
        db, background_tasks, image_bytes, image.content_type,
        user_id, category or None,
    )
    return CreateSessionResponse(**result)


@router.post("/sessions/{session_id}/next-round", response_model=NextRoundResponse)
async def next_round(
    session_id: str,
    body: NextRoundRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await session_service.handle_next_round(
            db, background_tasks, session_id, body.force,
        )
    except ValueError as e:
        status = 409 if "incomplete" in str(e).lower() else 400
        raise HTTPException(status, str(e))
    return NextRoundResponse(advanced=True, **result)


@router.post("/sessions/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize(
    session_id: str,
    body: FinalizeRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await session_service.handle_finalize(
            db, session_id, body.selected_candidate_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return FinalizeResponse(**result)
