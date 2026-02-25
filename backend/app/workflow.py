import asyncio
import uuid
from pathlib import Path
from .angles import ANGLES, BASE_PROMPT
from .generator import generate_one
from .jobs import (
    set_job_status,
    set_angle_done,
    set_angle_error,
    set_angle_processing,
    set_job_error,
)
from .config import settings


def _output_path(job_id: str, angle_key: str) -> Path:
    return settings.outputs_dir / f"{job_id}_{angle_key}.png"


def _filename(job_id: str, angle_key: str) -> str:
    return f"{job_id}_{angle_key}.png"


async def run_parallel(job_id: str, image_bytes: bytes, mime: str) -> None:
    """Generate all angles simultaneously from the original reference image."""
    set_job_status(job_id, "processing")

    async def _one(angle):
        set_angle_processing(job_id, angle.key)
        prompt = BASE_PROMPT + angle.suffix
        try:
            result = await generate_one(image_bytes, mime, prompt)
            path = _output_path(job_id, angle.key)
            path.write_bytes(result)
            set_angle_done(job_id, angle.key, _filename(job_id, angle.key))
        except Exception as exc:
            set_angle_error(job_id, angle.key, str(exc))

    await asyncio.gather(*[_one(angle) for angle in ANGLES])


async def run_sequential(job_id: str, image_bytes: bytes, mime: str) -> None:
    """Generate angles one-by-one, each feeding the previous output as reference."""
    set_job_status(job_id, "processing")
    current_bytes = image_bytes
    current_mime = mime

    for angle in ANGLES:
        set_angle_processing(job_id, angle.key)
        prompt = BASE_PROMPT + angle.suffix
        try:
            result = await generate_one(current_bytes, current_mime, prompt)
            path = _output_path(job_id, angle.key)
            path.write_bytes(result)
            set_angle_done(job_id, angle.key, _filename(job_id, angle.key))
            # Use this generated image as the reference for the next angle
            current_bytes = result
            current_mime = "image/png"
        except Exception as exc:
            set_angle_error(job_id, angle.key, str(exc))
            # On error, fall back to the original image for the next angle
            current_bytes = image_bytes
            current_mime = mime
