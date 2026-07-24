from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.pet_profile import PetSpecies


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    location_name: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    event_time: datetime = Field(description="Must be in the future")
    species: PetSpecies | None = Field(default=None, description="Leave unset to welcome all species")


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    location_name: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    event_time: datetime | None = None
    species: PetSpecies | None = None


class EventCreatorInfo(BaseModel):
    id: UUID
    full_name: str | None
    profile_photo_url: str | None

    model_config = {"from_attributes": True}


class EventResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    location_name: str
    latitude: float
    longitude: float
    event_time: datetime
    species: str | None
    creator: EventCreatorInfo
    attendee_count: int
    is_cancelled: bool
    your_rsvp_status: str | None
    created_at: datetime


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    limit: int
    offset: int


class EventRSVPRequest(BaseModel):
    pet_id: UUID | None = Field(default=None, description="Which of your pets is coming, if any")
    status: Literal["going", "interested"] = "going"


class EventRSVPResponse(BaseModel):
    id: UUID
    event_id: UUID
    status: str
    pet_id: UUID | None
    created_at: datetime


class AttendeePetInfo(BaseModel):
    id: UUID
    name: str
    species: str
    primary_photo_url: str | None


class AttendeeInfo(BaseModel):
    user_id: UUID
    full_name: str | None
    profile_photo_url: str | None
    status: str
    pet: AttendeePetInfo | None


class EventAttendeesResponse(BaseModel):
    items: list[AttendeeInfo]
    total: int
