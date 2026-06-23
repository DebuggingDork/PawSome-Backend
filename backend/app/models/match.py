import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Match(Base):
    """Mutual likes between two pets - created when both pets like each other"""
    
    __tablename__ = "matches"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Pet 1 (we store smaller UUID first for consistency)
    pet1_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pet_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Pet 2 (larger UUID)
    pet2_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pet_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Soft-delete for unmatch functionality
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    __table_args__ = (
        # Ensure unique match pair
        UniqueConstraint("pet1_id", "pet2_id", name="uq_match_pair"),
        # Indexes for querying matches
        Index("ix_matches_pet1", "pet1_id"),
        Index("ix_matches_pet2", "pet2_id"),
        # Index for filtering soft-deleted matches
        Index("ix_matches_deleted_at", "deleted_at"),
    )
