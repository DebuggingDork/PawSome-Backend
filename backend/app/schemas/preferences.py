from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class UpdatePreferencesRequest(BaseModel):
    preferred_match_radius_km: float | None = Field(default=None, ge=1, le=500)
    preferred_species: str | None = None
    preferred_age_min: int | None = Field(default=None, ge=0)
    preferred_age_max: int | None = Field(default=None, ge=0)
    preferred_gender: str | None = None
    breed_preferences: list[str] | None = None

    @model_validator(mode="after")
    def validate_age_range(self) -> "UpdatePreferencesRequest":
        if self.preferred_age_min is not None and self.preferred_age_max is not None:
            if self.preferred_age_min > self.preferred_age_max:
                raise ValueError(
                    "preferred_age_min must be less than or equal to preferred_age_max"
                )
        return self


class MatchPreferenceResponse(BaseModel):
    id: UUID
    user_id: UUID
    preferred_species: str | None
    preferred_age_min: int | None
    preferred_age_max: int | None
    preferred_gender: str | None
    preferred_radius_km: float | None
    breed_preferences: list[str] | None
    updated_at: datetime

    model_config = {"from_attributes": True}
