from pydantic import BaseModel
from typing import Literal


class FeedbackRequest(BaseModel):
    candidate_id: str
    action: Literal["like", "dislike", "save"]
    reason_tags: list[str] = []
    text_note: str | None = None
    chip_dimension_map: dict[str, list[str]] = {}


class FeedbackResponse(BaseModel):
    feedback_accepted: bool
    reward: float
