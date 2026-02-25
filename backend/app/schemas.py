from pydantic import BaseModel, Field
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


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str
    round_number: int
    candidates: list[CandidateOut]


class CandidatesResponse(BaseModel):
    session_id: str
    round_number: int
    candidates: list[CandidateOut]


class FeedbackRequest(BaseModel):
    candidate_id: str
    action: Literal["like", "dislike", "save"]
    reason_tags: list[str] = []
    text_note: str | None = None
    chip_dimension_map: dict[str, list[str]] = {}  # dynamic chip→dim map, round-tripped from frontend


class FeedbackResponse(BaseModel):
    feedback_accepted: bool
    reward: float


class NextRoundRequest(BaseModel):
    force: bool = False


class NextRoundResponse(BaseModel):
    advanced: bool
    round_number: int
    next_candidates: list[CandidateOut] = Field(default_factory=list)


class FinalizeRequest(BaseModel):
    selected_candidate_id: str


class FinalizeResponse(BaseModel):
    session_id: str
    hero_image_url: str
    export_variants: dict[str, str]
