from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlaydateCreate(BaseModel):
    scheduled_at: datetime = Field(description="Must be in the future")
    location_name: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=1000)


class PlaydateRespondRequest(BaseModel):
    status: Literal["accepted", "declined"]


class PlaydatePetInfo(BaseModel):
    id: UUID
    name: str
    primary_photo_url: str | None

    model_config = {"from_attributes": True}


class PlaydateResponse(BaseModel):
    id: UUID
    match_id: UUID
    scheduled_at: datetime
    location_name: str
    latitude: float
    longitude: float
    note: str | None
    status: str
    proposed_by_pet: PlaydatePetInfo
    proposed_to_pet: PlaydatePetInfo
    is_mine_to_respond: bool = Field(description="True if the caller is the recipient and status is pending")
    created_at: datetime
    responded_at: datetime | None


class PlaydateListResponse(BaseModel):
    items: list[PlaydateResponse]
    total: int
