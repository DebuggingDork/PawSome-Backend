import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AchievementType(str, enum.Enum):
    PROFILE_PHOTO = "profile_photo"
    FULL_NAME = "full_name"
    PET_CREATED = "pet_created"
    PET_PHOTO = "pet_photo"
    FIRST_MATCH = "first_match"
    FIVE_MATCHES = "five_matches"
    FIRST_MESSAGE = "first_message"
    PROFILE_COMPLETE = "profile_complete"
    VERIFIED_EMAIL = "verified_email"


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
