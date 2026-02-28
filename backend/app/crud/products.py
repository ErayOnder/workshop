from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Product


async def create_product(
    db: AsyncSession, user_id: str, category: str | None, image_filename: str
) -> Product:
    product = Product(user_id=user_id, category=category, image_filename=image_filename)
    db.add(product)
    await db.flush()
    return product


async def get_product(db: AsyncSession, product_id: str) -> Product | None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    return result.scalar_one_or_none()
