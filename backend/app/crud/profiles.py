from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import UserPreferenceProfile, UserPreferenceDimension
from ..core.dimensions import ALL_DIMENSIONS


async def get_or_create_profile(db: AsyncSession, user_id: str) -> UserPreferenceProfile:
    result = await db.execute(
        select(UserPreferenceProfile).where(UserPreferenceProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserPreferenceProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
        # Initialize all 14 dimensions at zero
        for dim_name in ALL_DIMENSIONS:
            dim = UserPreferenceDimension(profile_id=profile.id, dimension_name=dim_name)
            db.add(dim)
        await db.flush()
    return profile


async def get_dimensions(db: AsyncSession, profile_id: str) -> dict[str, UserPreferenceDimension]:
    result = await db.execute(
        select(UserPreferenceDimension).where(UserPreferenceDimension.profile_id == profile_id)
    )
    dims = result.scalars().all()
    dim_map = {d.dimension_name: d for d in dims}
    # Ensure all dimensions exist
    for dim_name in ALL_DIMENSIONS:
        if dim_name not in dim_map:
            new_dim = UserPreferenceDimension(profile_id=profile_id, dimension_name=dim_name)
            db.add(new_dim)
            dim_map[dim_name] = new_dim
    await db.flush()
    return dim_map


async def upsert_dimension(
    db: AsyncSession,
    profile_id: str,
    dimension_name: str,
    score: float,
    confidence: float,
    interaction_count: int,
) -> None:
    result = await db.execute(
        select(UserPreferenceDimension).where(
            UserPreferenceDimension.profile_id == profile_id,
            UserPreferenceDimension.dimension_name == dimension_name,
        )
    )
    dim = result.scalar_one_or_none()
    if dim is None:
        dim = UserPreferenceDimension(
            profile_id=profile_id,
            dimension_name=dimension_name,
            score=score,
            confidence=confidence,
            interaction_count=interaction_count,
        )
        db.add(dim)
    else:
        dim.score = score
        dim.confidence = confidence
        dim.interaction_count = interaction_count
        dim.last_updated = datetime.utcnow()
    await db.flush()


async def increment_profile_interactions(db: AsyncSession, profile: UserPreferenceProfile) -> None:
    profile.total_interactions += 1
    profile.last_updated = datetime.utcnow()
    await db.flush()
