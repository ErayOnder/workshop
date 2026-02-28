from fastapi import APIRouter
from .sessions import router as sessions_router
from .candidates import router as candidates_router
from .feedback import router as feedback_router
from .images import router as images_router

router = APIRouter()
router.include_router(sessions_router)
router.include_router(candidates_router)
router.include_router(feedback_router)
router.include_router(images_router)
