from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.user_achievement import AchievementType


class AchievementResponse(BaseModel):
    id: UUID
    achievement_type: AchievementType
    earned_at: datetime

    model_config = {
        "from_attributes": True,
    }


class AchievementBadge(BaseModel):
    """Badge information with display data"""
    type: AchievementType
    name: str = Field(description="Display name")
    description: str = Field(description="What this achievement represents")
    icon: str = Field(description="Emoji or icon identifier")
    earned: bool = Field(description="Whether user has earned this")
    earned_at: datetime | None = Field(description="When it was earned")


class AchievementSummary(BaseModel):
    """User's achievement progress"""
    total_earned: int
    total_available: int
    completion_percentage: int
    badges: list[AchievementBadge]
    recent_achievements: list[AchievementResponse]
    # Badges awarded by this very request, i.e. the user qualified for them but
    # had not been given them yet. The client celebrates these; on the next read
    # they are already held and the list is empty, so a badge is announced once.
    newly_earned: list[AchievementBadge] = Field(default_factory=list)
