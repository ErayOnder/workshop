from fastapi import APIRouter
from .sessions import router as sessions_router
from .images import router as images_router

router = APIRouter()
router.include_router(sessions_router)
router.include_router(images_router)
