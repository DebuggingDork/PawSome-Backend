from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """Breakdown of individual scoring components for a match suggestion."""

    breed: int
    distance: int
    age: int
    gender: int


class MatchSuggestionResponse(BaseModel):
    """A single smart match suggestion with compatibility score and distance."""

    pet: dict  # PetPublicResponse data
    match_score: int = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    distance_km: float


class SuggestionsListResponse(BaseModel):
    """Paginated list of smart match suggestions."""

    suggestions: list[MatchSuggestionResponse]
    total: int
    scoring_version: str = "v1.0"
