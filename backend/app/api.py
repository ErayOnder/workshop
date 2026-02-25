import asyncio
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .config import settings
from .jobs import create_job, get_job
from .schemas import GenerateResponse, JobStatus
from .workflow import run_parallel, run_sequential

router = APIRouter()

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MIME_TO_EXT = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp"}


@router.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    mode: Literal["parallel", "sequential"] = Form("parallel"),
):
    if image.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {image.content_type}. Use JPEG, PNG, or WebP.",
        )

    image_bytes = await image.read()
    mime = image.content_type
    job_id = str(uuid.uuid4())

    create_job(job_id, mode)

    if mode == "parallel":
        background_tasks.add_task(run_parallel, job_id, image_bytes, mime)
    else:
        background_tasks.add_task(run_sequential, job_id, image_bytes, mime)

    return GenerateResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/images/{filename}")
async def serve_image(filename: str):
    # Sanitize: only allow alphanumerics, hyphens, underscores, dots
    if not all(c.isalnum() or c in "-_." for c in filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = settings.outputs_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")
