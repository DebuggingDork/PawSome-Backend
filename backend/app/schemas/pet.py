from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.pet_profile import PetSpecies


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    species: PetSpecies
    breed: str = Field(min_length=1, max_length=100)
    age_months: int = Field(gt=0, le=600, description="Age in months")
    gender: Literal["male", "female"]
    bio: str | None = Field(default=None, max_length=2000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    species: PetSpecies | None = None
    breed: str | None = Field(default=None, min_length=1, max_length=100)
    age_months: int | None = Field(default=None, gt=0, le=600)
    gender: Literal["male", "female"] | None = None
    bio: str | None = Field(default=None, max_length=2000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class PetPublicResponse(BaseModel):
    """What other users see when browsing — never exposes exact coordinates."""

    id: UUID
    name: str
    species: PetSpecies
    breed: str
    age_months: int
    gender: str
    bio: str | None
    is_active: bool
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class PetResponse(PetPublicResponse):
    """Full pet data, returned only to the owner."""

    user_id: UUID
    lat: float
    lng: float
    updated_at: datetime
