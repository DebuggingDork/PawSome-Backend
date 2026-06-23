from datetime import datetime

from pydantic import BaseModel


class MatchCandidateResponse(BaseModel):
    pet: dict  # holds PetPublicResponse data
    distance_km: float
    calculated_at: datetime


class BrowsePetsResponse(BaseModel):
    candidates: list[MatchCandidateResponse]
    total: int
    filters_applied: dict
