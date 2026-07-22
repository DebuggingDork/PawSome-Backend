from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SwipeRequest(BaseModel):
    """Request to swipe on a pet"""
    pet_id: UUID  # Your pet doing the swiping
    target_pet_id: UUID  # The pet you're swiping on
    action: Literal["like", "skip"]


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


class MatchWithPetDetails(BaseModel):
    """Match with full pet details for display"""
    id: UUID
    created_at: datetime
    matched_pet: dict  # PetPublicResponse
    your_pet: dict  # PetResponse


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
    created_at: datetime
    read_at: datetime | None
    your_pet: dict  # Basic pet info
    other_pet: dict  # Basic pet info
    match_id: UUID | None


class MarkNotificationReadRequest(BaseModel):
    """Mark notifications as read"""
    notification_ids: list[UUID]
