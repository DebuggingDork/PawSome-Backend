import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SwipeAction(str, enum.Enum):
    LIKE = "like"  # Right swipe
    SKIP = "skip"  # Left swipe


class Swipe(Base):
    """Records every swipe action - user's pet swiped on target pet"""
    
    __tablename__ = "swipes"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # The pet doing the swiping
    swiper_pet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pet_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # The pet being swiped on
    target_pet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pet_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    action: Mapped[SwipeAction] = mapped_column(
        Enum(SwipeAction, name="swipe_action", native_enum=False, length=20),
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Undo functionality fields
    is_undone: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    
    undone_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    __table_args__ = (
        # One swipe per pet pair - can't swipe twice on same pet
        UniqueConstraint("swiper_pet_id", "target_pet_id", name="uq_swipe_pair"),
        # Index for finding mutual likes
        Index("ix_swipes_target_action", "target_pet_id", "action"),
        # Index for time-based queries (undo window)
        Index("ix_swipes_created_at", "created_at"),
    )
