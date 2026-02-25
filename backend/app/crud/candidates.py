from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Candidate


async def create_candidate(
    db: AsyncSession,
    session_id: str,
    round_number: int,
    generation_config: dict,
    rendered_prompt: str,
) -> Candidate:
    candidate = Candidate(
        session_id=session_id,
        round_number=round_number,
        generation_config=generation_config,
        rendered_prompt=rendered_prompt,
        generation_status="pending",
    )
    db.add(candidate)
    await db.flush()
    return candidate


async def get_candidate(db: AsyncSession, candidate_id: str) -> Candidate | None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    return result.scalar_one_or_none()


async def get_candidates_for_round(
    db: AsyncSession, session_id: str, round_number: int
) -> list[Candidate]:
    result = await db.execute(
        select(Candidate)
        .where(Candidate.session_id == session_id, Candidate.round_number == round_number)
        .order_by(Candidate.created_at)
    )
    return list(result.scalars().all())


async def set_candidate_generating(db: AsyncSession, candidate_id: str) -> None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate:
        candidate.generation_status = "generating"
        await db.flush()


async def set_candidate_done(db: AsyncSession, candidate_id: str, filename: str) -> None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate:
        candidate.generation_status = "done"
        candidate.image_filename = filename
        await db.flush()


async def set_candidate_error(db: AsyncSession, candidate_id: str, error: str) -> None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate:
        candidate.generation_status = "error"
        candidate.generation_error = error
        await db.flush()


async def set_candidate_analysis_running(db: AsyncSession, candidate_id: str) -> None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate:
        candidate.analysis_status = "running"
        await db.flush()


async def set_candidate_analysis_done(
    db: AsyncSession,
    candidate_id: str,
    image_analysis: dict,
    chip_dimension_map: dict,
) -> None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate:
        candidate.analysis_status = "done"
        candidate.image_analysis = image_analysis
        candidate.chip_dimension_map = chip_dimension_map
        await db.flush()


async def set_candidate_analysis_failed(db: AsyncSession, candidate_id: str) -> None:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if candidate:
        candidate.analysis_status = "failed"
        await db.flush()
