import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..db.models import Candidate
from ..schemas.candidates import CandidateOut, CandidatesResponse, ImageAnalysisData
from ..crud.sessions import get_session
from ..crud.candidates import get_candidates_for_round
from ..core.sse_bus import subscribe, unsubscribe

router = APIRouter(tags=["candidates"])
logger = logging.getLogger(__name__)


def candidate_to_out(c: Candidate) -> CandidateOut:
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
        image_url=f"/v1/images/{c.image_filename}" if c.image_filename else None,
        error=c.generation_error,
        analysis_status=c.analysis_status,  # type: ignore[arg-type]
        image_analysis=analysis,
    )


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
        candidates=[candidate_to_out(c) for c in candidates],
    )


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
            # If no candidates exist yet (pipeline hasn't created them),
            # skip the replay phase and go straight to listening for events.
            all_settled = len(candidates) > 0
            for c in candidates:
                if c.generation_status in ("done", "error"):
                    yield _sse("candidate_done", {
                        "candidate_id": c.id,
                        "generation_status": c.generation_status,
                        "image_url": f"/v1/images/{c.image_filename}" if c.image_filename else None,
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
