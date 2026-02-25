from pydantic import BaseModel
from typing import Literal


class AngleStatus(BaseModel):
    status: Literal["pending", "processing", "done", "error"]
    file: str | None = None
    error: str | None = None


class JobStatus(BaseModel):
    job_id: str
    mode: Literal["parallel", "sequential"]
    status: Literal["pending", "processing", "completed", "failed"]
    angles: dict[str, AngleStatus]
    error: str | None = None


class GenerateResponse(BaseModel):
    job_id: str
