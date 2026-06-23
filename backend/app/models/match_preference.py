import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class MatchPreference(Base):
    """
    User preferences for filtering potential matches.
    Each user can have exactly one preference record.
    """
    __tablename__ = "match_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    preferred_species: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    preferred_age_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    preferred_age_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    preferred_gender: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    preferred_radius_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=50.0,
    )

    breed_preferences: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="match_preference")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_one_preference_per_user"),
        CheckConstraint(
            "preferred_age_min IS NULL OR preferred_age_max IS NULL OR preferred_age_min <= preferred_age_max",
            name="ck_age_range_valid"
        ),
        CheckConstraint(
            "preferred_radius_km IS NULL OR (preferred_radius_km >= 1 AND preferred_radius_km <= 500)",
            name="ck_radius_valid"
        ),
    )
