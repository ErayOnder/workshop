from pydantic import BaseModel
from typing import Literal


class CandidateOut(BaseModel):
    candidate_id: str
    generation_status: Literal["pending", "generating", "done", "error"]
    image_url: str | None = None
    error: str | None = None


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


class FeedbackResponse(BaseModel):
    feedback_accepted: bool
    reward: float
    next_candidates: list[CandidateOut]


class FinalizeRequest(BaseModel):
    selected_candidate_id: str


class FinalizeResponse(BaseModel):
    session_id: str
    hero_image_url: str
    export_variants: dict[str, str]
