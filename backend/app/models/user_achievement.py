import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AchievementType(str, enum.Enum):
    """Badge identifiers.

    Declaration order is display order in the Badges tab, so these run roughly
    from "you just signed up" to "you have been here a while". Stored as a
    non-native enum (a VARCHAR with a check constraint), so adding members needs
    no migration.
    """

    # Setting up
    FULL_NAME = "full_name"
    VERIFIED_EMAIL = "verified_email"
    PROFILE_PHOTO = "profile_photo"
    ON_THE_MAP = "on_the_map"
    STORYTELLER = "storyteller"
    PET_CREATED = "pet_created"
    PET_PHOTO = "pet_photo"
    PROFILE_COMPLETE = "profile_complete"

    # Getting out there
    FIRST_SWIPE = "first_swipe"
    FIFTY_SWIPES = "fifty_swipes"
    SUPER_WOOF = "super_woof"
    FIRST_MATCH = "first_match"
    FIVE_MATCHES = "five_matches"
    TEN_MATCHES = "ten_matches"

    # Actually talking to people
    FIRST_MESSAGE = "first_message"
    HUNDRED_MESSAGES = "hundred_messages"
    FIRST_PLAYDATE = "first_playdate"
    PLAYDATE_CONFIRMED = "playdate_confirmed"

    # Sticking around
    FULL_GALLERY = "full_gallery"
    MULTI_PET = "multi_pet"
    WEEK_ONE = "week_one"


class UserAchievement(Base):
    """Track user achievements and badges"""
    
    __tablename__ = "user_achievements"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    achievement_type: Mapped[AchievementType] = mapped_column(
        Enum(AchievementType, name="achievement_type", native_enum=False, length=50),
        nullable=False,
    )
    
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_type", name="uq_user_achievement"),
    )
