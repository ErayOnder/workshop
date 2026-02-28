from pydantic import BaseModel

from .candidates import CandidateOut


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str
    round_number: int


class NextRoundRequest(BaseModel):
    force: bool = False


class NextRoundResponse(BaseModel):
    advanced: bool
    round_number: int


class FinalizeRequest(BaseModel):
    selected_candidate_id: str


class FinalizeResponse(BaseModel):
    session_id: str
    hero_image_url: str
    export_variants: dict[str, str]
