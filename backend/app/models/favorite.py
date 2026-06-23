import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Favorite(Base):
    """Records pet bookmarks - user's pet favorites another pet for later review"""
    
    __tablename__ = "favorites"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # The pet doing the favoriting (user's pet)
    pet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pet_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # The pet being favorited (target pet)
    target_pet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pet_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Soft-delete timestamp for analytics preservation
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )
    
    __table_args__ = (
        # Ensure unique favorite pair (one favorite per pet pair)
        UniqueConstraint("pet_id", "target_pet_id", name="uq_favorite_pair"),
        # Prevent self-favoriting
        CheckConstraint("pet_id != target_pet_id", name="ck_no_self_favorite"),
        # Index for querying favorites by pet
        Index("ix_favorites_pet_id", "pet_id"),
        # Index for filtering by deleted status
        Index("ix_favorites_deleted_at", "deleted_at"),
    )
