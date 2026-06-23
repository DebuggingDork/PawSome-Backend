import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


if TYPE_CHECKING:
    from app.models.pet_photo import PetPhoto
    from app.models.user import User


class PetSpecies(str, enum.Enum):
    DOG = "dog"
    CAT = "cat"
    RABBIT = "rabbit"
    BIRD = "bird"
    OTHER = "other"


class PetProfile(Base):
    __tablename__ = "pet_profiles"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    species: Mapped[PetSpecies] = mapped_column(
        Enum(PetSpecies, name="pet_species", native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    breed: Mapped[str] = mapped_column(String(100), nullable=False)
    age_months: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)  # male/female
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Health certification fields
    is_vaccinated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vaccination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_neutered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_trained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    user: Mapped["User"] = relationship(back_populates="pet_profiles")

    # lazy="selectin": photos are always eagerly loaded (max 5 per pet), so
    # response schemas can safely access them in async context anywhere.
    photos: Mapped[list["PetPhoto"]] = relationship(
        back_populates="pet",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PetPhoto.sort_order",
    )

    @property
    def primary_photo_url(self) -> str | None:
        primary = next((p for p in self.photos if p.is_primary), None)
        if primary is not None:
            return primary.url
        return self.photos[0].url if self.photos else None