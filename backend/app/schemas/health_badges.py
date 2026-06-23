from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


class UpdateHealthBadgesRequest(BaseModel):
    is_vaccinated: bool
    vaccination_date: date | None = None
    is_neutered: bool
    is_trained: bool


class VaccinationStatus(BaseModel):
    status: bool
    date: date | None
    is_current: bool  # True if vaccination_date is within 365 days
    days_until_update: int | None  # Days remaining; None if not vaccinated

    @model_validator(mode="before")
    @classmethod
    def compute_derived_fields(cls, values: dict) -> dict:
        """Compute is_current and days_until_update from status and date."""
        status = values.get("status", False)
        vaccination_date = values.get("date")

        if not status or vaccination_date is None:
            values["is_current"] = False
            values["days_until_update"] = None
            return values

        today = date.today()
        days_elapsed = (today - vaccination_date).days
        days_remaining = 365 - days_elapsed

        values["is_current"] = days_elapsed <= 365
        values["days_until_update"] = max(days_remaining, 0) if days_remaining >= 0 else None
        return values

    model_config = {
        "from_attributes": True,
    }


class HealthBadgesDetail(BaseModel):
    vaccinated: VaccinationStatus
    neutered: bool
    trained: bool

    model_config = {
        "from_attributes": True,
    }


class HealthBadgesResponse(BaseModel):
    pet_id: UUID
    health_badges: HealthBadgesDetail
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }
