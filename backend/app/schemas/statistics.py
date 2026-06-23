from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DailySwipeStats(BaseModel):
    """Swipe statistics for a single day"""
    date: str  # YYYY-MM-DD
    likes: int
    skips: int


class TopBreed(BaseModel):
    """A breed and how many times it was liked"""
    breed: str
    count: int


class SwipeStatisticsResponse(BaseModel):
    """Aggregated swipe statistics for a pet"""
    pet_id: UUID
    total_likes: int
    total_skips: int
    like_to_skip_ratio: float
    matches_created: int
    avg_response_time_minutes: float | None
    last_30_days: list[DailySwipeStats]
    top_breeds_liked: list[TopBreed]


class SwipeHistoryItem(BaseModel):
    """A single swipe record with target pet details"""
    swipe_id: UUID
    action: str
    created_at: datetime
    target_pet: dict

    model_config = {"from_attributes": True}


class SwipeHistoryResponse(BaseModel):
    """Paginated swipe history for a pet"""
    swipes: list[SwipeHistoryItem]
    total: int
    limit: int
    offset: int
