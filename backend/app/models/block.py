import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Block(Base):
    """Records user blocking relationships for safety controls"""
    
    __tablename__ = "blocks"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # The user initiating the block
    blocking_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # The user being blocked
    blocked_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        # Unique constraint on blocking pair
        UniqueConstraint("blocking_user_id", "blocked_user_id", name="uq_block_pair"),
        # Index on blocking_user_id for fast lookups
        Index("ix_blocks_blocking_user", "blocking_user_id"),
        # Index on blocked_user_id for fast lookups
        Index("ix_blocks_blocked_user", "blocked_user_id"),
        # Prevent self-blocking
        CheckConstraint("blocking_user_id != blocked_user_id", name="ck_no_self_block"),
    )
