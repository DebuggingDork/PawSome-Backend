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
    # True when this card is one the caller passed on earlier and is being shown
    # again because the unseen pets ran out. The UI labels these so a familiar
    # face doesn't read as a bug.
    previously_passed: bool = False


class BrowsePetsResponse(BaseModel):
    candidates: list[MatchCandidateResponse]
    total: int
    filters_applied: dict
