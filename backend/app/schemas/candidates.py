from pydantic import BaseModel
from typing import Literal


class DynamicChip(BaseModel):
    id: str
    label: str
    dimensions: list[str]


class ImageAnalysisData(BaseModel):
    like_chips: list[DynamicChip]
    dislike_chips: list[DynamicChip]
    chip_dimension_map: dict[str, list[str]]


class CandidateOut(BaseModel):
    candidate_id: str
    generation_status: Literal["pending", "generating", "done", "error"]
    image_url: str | None = None
    error: str | None = None
    analysis_status: Literal["pending", "running", "done", "failed"] = "pending"
    image_analysis: ImageAnalysisData | None = None


class CandidatesResponse(BaseModel):
    session_id: str
    round_number: int
    candidates: list[CandidateOut]
