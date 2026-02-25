import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter(tags=["images"])

_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


@router.get("/images/{filename}")
async def serve_image(filename: str):
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(400, "Invalid filename")

    # Search outputs first, then uploads
    for directory in (settings.outputs_dir, settings.uploads_dir):
        path = directory / filename
        if path.exists():
            return FileResponse(str(path), media_type="image/png")

    raise HTTPException(404, "Image not found")
