from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Session, User, Product


async def ensure_user(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=user_id)
        db.add(user)
        await db.flush()
    return user


async def create_product(
    db: AsyncSession, user_id: str, category: str | None, image_filename: str
) -> Product:
    product = Product(user_id=user_id, category=category, image_filename=image_filename)
    db.add(product)
    await db.flush()
    return product


async def create_session(db: AsyncSession, user_id: str, product_id: str) -> Session:
    session = Session(user_id=user_id, product_id=product_id, round_number=0)
    db.add(session)
    await db.flush()
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def increment_round(db: AsyncSession, session: Session) -> int:
    session.round_number += 1
    await db.flush()
    return session.round_number


async def finalize_session(db: AsyncSession, session: Session) -> None:
    session.status = "finalized"
    session.finalized_at = datetime.utcnow()
    await db.flush()


_EMPTY_CONTEXT: dict = {
    "structural": {},
    "corrections": [],
    "scene_history": [],
    "liked_tags": [],
    "disliked_tags": [],
}


async def get_creative_context(db: AsyncSession, session_id: str) -> dict:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None or session.creative_context is None:
        return dict(_EMPTY_CONTEXT)
    return dict(session.creative_context)


async def save_creative_context(db: AsyncSession, session: Session, context: dict) -> None:
    session.creative_context = context
    await db.flush()
