from datetime import datetime

from pydantic import BaseModel


class MatchCandidateResponse(BaseModel):
    pet: dict  # holds PetPublicResponse data
    # None when the owner hasn't set a location. Those pets used to be dropped
    # from the deck entirely, which quietly hid every owner who skipped the
    # location step; an unknown distance is worth showing, just ranked last.
    distance_km: float | None
    calculated_at: datetime
    compatibility_score: int | None = None  # 0-100; only set when browsing with a pet_id


class BrowsePetsResponse(BaseModel):
    candidates: list[MatchCandidateResponse]
    total: int
    filters_applied: dict
