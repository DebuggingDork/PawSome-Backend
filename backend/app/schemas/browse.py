from datetime import datetime

from pydantic import BaseModel


class MatchCandidateResponse(BaseModel):
    pet: dict  # holds PetPublicResponse data
    distance_km: float
    calculated_at: datetime
    compatibility_score: int | None = None  # 0-100; only set when browsing with a pet_id


class BrowsePetsResponse(BaseModel):
    candidates: list[MatchCandidateResponse]
    total: int
    filters_applied: dict
