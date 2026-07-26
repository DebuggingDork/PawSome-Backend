from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AqiBand = Literal[
    "good",
    "moderate",
    "unhealthy_sensitive",
    "unhealthy",
    "very_unhealthy",
    "hazardous",
]


class ConditionsResponse(BaseModel):
    """Weather and air quality at one place, at one hour.

    Everything past `available` is optional because the two upstream feeds have
    different horizons (16 days for weather, 7 for air quality) and either can
    fail independently — a card showing temperature with no AQI is fine, a card
    that errors because one feed was down is not.
    """

    available: bool
    observed_for: datetime | None = None

    temperature_c: float | None = None
    precipitation_probability: int | None = None
    weather_code: int | None = None
    summary: str | None = None
    wind_speed_kmh: float | None = None

    us_aqi: int | None = None
    aqi_band: AqiBand | None = None
