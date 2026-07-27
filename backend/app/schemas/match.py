from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.pet import PetPublicResponse


class SwipeRequest(BaseModel):
    """Request to swipe on a pet"""
    pet_id: UUID  # Your pet doing the swiping
    target_pet_id: UUID  # The pet you're swiping on
    action: Literal["like", "skip", "super_like"]


class SwipeResponse(BaseModel):
    """Response after a swipe"""
    id: UUID  # The swipe's own id, needed by POST /matches/undo-swipe
    swiper_pet_id: UUID
    target_pet_id: UUID
    action: str
    is_match: bool  # True if this created a mutual match
    match_id: UUID | None  # Only present if is_match is True
    created_at: datetime
    
    model_config = {
        "from_attributes": True,
    }


class MatchResponse(BaseModel):
    """Information about a match"""
    id: UUID
    pet1_id: UUID
    pet2_id: UUID
    created_at: datetime
    
    model_config = {
        "from_attributes": True,
    }


class MatchSummaryResponse(MatchResponse):
    """A match with the other side already resolved.

    The Matches and Chat screens need the *other* pet for every match, and used
    to fetch it themselves with one GET /pets/{id} per match. That endpoint only
    serves active pets, so a single deactivated pet anywhere in the list took the
    whole list down with it — every match vanished from both screens. Resolving
    the pet here means one query instead of N requests, and a pet whose owner has
    since deactivated it still renders (the conversation and its history are
    real either way)."""

    your_pet_id: UUID
    other_pet: PetPublicResponse


class MatchWithPetDetails(BaseModel):
    """Match with full pet details for display"""
    id: UUID
    created_at: datetime
    matched_pet: dict  # PetPublicResponse
    your_pet: dict  # PetResponse


class PetRelationshipResponse(BaseModel):
    """How the caller already stands with a given pet — drives whether the
    Community card offers "Interested" or reports an existing match."""

    pet_id: UUID
    status: Literal["none", "own", "liked", "skipped", "matched", "no_pet"]
    match_id: UUID | None = None
    your_pet_id: UUID | None = None


class NotificationResponse(BaseModel):
    """User notification"""
    id: UUID
    notification_type: str
    pet_id: UUID  # Your pet
    related_pet_id: UUID  # Other pet involved
    match_id: UUID | None
    message: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None
    
    model_config = {
        "from_attributes": True,
    }


class NotificationWithDetails(BaseModel):
    """Notification with pet details"""
    id: UUID
    notification_type: str
    message: str
    is_read: bool
    is_super: bool = False
    created_at: datetime
    read_at: datetime | None
    your_pet: dict  # Basic pet info
    other_pet: dict  # Basic pet info
    match_id: UUID | None


class MarkNotificationReadRequest(BaseModel):
    """Mark notifications as read"""
    notification_ids: list[UUID]


class SuperWoofStatus(BaseModel):
    """How many Super Woofs the caller has left in the current 24h window"""
    remaining: int
    limit: int
    window_seconds: int
