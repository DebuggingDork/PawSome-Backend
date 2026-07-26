"""Weather + air quality for a place and time, via Open-Meteo.

Why this is a backend proxy rather than a browser fetch, even though Open-Meteo
sends permissive CORS headers: caching. Ten owners looking at playdates in the
same park at the same hour all want one identical answer, and routing through
Redis here turns that into one upstream call instead of ten. That keeps us
inside Open-Meteo's fair-use expectations as the user count grows, and it's the
same shape as the Nominatim proxy in `geocoding.py`.

Open-Meteo needs no API key for non-commercial use. Data is CC BY 4.0.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis

from app.api.deps import get_current_user_optional
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.conditions import AqiBand, ConditionsResponse
from app.services.api_cache import cached_json, geo_key
from app.services.external_http import UpstreamUnavailable, fetch_json

router = APIRouter(prefix="/conditions", tags=["conditions"])

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Open-Meteo's published horizons. Asking beyond them returns an error rather
# than a partial answer, so we check before spending a request.
WEATHER_HORIZON_DAYS = 16
AIR_QUALITY_HORIZON_DAYS = 7

CACHE_TTL_SECONDS = 30 * 60

# WMO 4677 weather codes, collapsed to what fits on a card. The exact
# distinctions upstream draws (slight vs moderate vs dense drizzle) are more
# resolution than anyone deciding whether to walk a dog needs.
WMO_SUMMARY: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}

# US EPA AQI breakpoints.
AQI_BANDS: list[tuple[int, AqiBand]] = [
    (50, "good"),
    (100, "moderate"),
    (150, "unhealthy_sensitive"),
    (200, "unhealthy"),
    (300, "very_unhealthy"),
]


def _aqi_band(aqi: int) -> AqiBand:
    for ceiling, band in AQI_BANDS:
        if aqi <= ceiling:
            return band
    return "hazardous"


def _as_utc(value: datetime) -> datetime:
    """A naive datetime from a client is assumed UTC rather than rejected —
    every caller we control sends an offset, and guessing the server's local
    zone would be worse than assuming the one the API documents."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _nearest_index(times: list[int], target_epoch: int) -> int | None:
    """Index of the hourly sample closest to the target instant.

    Open-Meteo returns whole hours; a playdate at 18:30 should read the 18:00
    sample rather than falling through to "no data".
    """
    if not times:
        return None
    return min(range(len(times)), key=lambda i: abs(times[i] - target_epoch))


def _value_at(payload: dict[str, Any], field: str, index: int) -> Any:
    """Pull one hourly value, tolerating a field the upstream omitted.

    Open-Meteo drops variables it has no data for instead of returning nulls,
    so a missing key is normal, not a bug.
    """
    series = (payload.get("hourly") or {}).get(field)
    if not isinstance(series, list) or index >= len(series):
        return None
    return series[index]


async def _fetch_hourly(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """One upstream feed. Returns None on failure — the caller renders whatever
    it did get, because half a badge beats a broken card."""
    try:
        return await fetch_json(client, url, params=params)
    except UpstreamUnavailable:
        return None


@router.get("", response_model=ConditionsResponse)
async def get_conditions(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    at: datetime = Query(..., description="When the meetup happens (ISO 8601)"),
    redis: Redis = Depends(get_redis),
    user: User | None = Depends(get_current_user_optional),
) -> ConditionsResponse:
    """Conditions at `lat`/`lng` for the hour containing `at`.

    Public (optional auth) because community events are browsable while signed
    out, and an event card should look the same either way.
    """
    target = _as_utc(at)
    now = datetime.now(timezone.utc)
    days_out = (target - now).total_seconds() / 86400

    # Nothing to forecast for a date that's passed or beyond the model horizon.
    # Checked before any network call so a chat full of old playdates costs
    # nothing.
    if days_out < 0 or days_out > WEATHER_HORIZON_DAYS:
        return ConditionsResponse(available=False)

    target_epoch = int(target.timestamp())
    hour_bucket = target_epoch // 3600

    async def load() -> dict[str, Any]:
        # UTC + unixtime throughout: the alternative (timezone=auto) returns
        # local wall-clock strings with no offset, which we'd then have to
        # re-interpret against the venue's zone to find the right hour.
        day = target.date().isoformat()
        common = {
            "latitude": lat,
            "longitude": lng,
            "timezone": "UTC",
            "timeformat": "unixtime",
            "start_date": day,
            "end_date": day,
        }

        forecast_params = {
            **common,
            "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
        }
        air_params = {**common, "hourly": "us_aqi"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            requests: list[Any] = [_fetch_hourly(client, FORECAST_URL, forecast_params)]
            # Air quality has a shorter horizon than weather; past it, skip the
            # call entirely rather than trading a request for a guaranteed error.
            if days_out <= AIR_QUALITY_HORIZON_DAYS:
                requests.append(_fetch_hourly(client, AIR_QUALITY_URL, air_params))

            results = await asyncio.gather(*requests)

        forecast = results[0]
        air = results[1] if len(results) > 1 else None

        result: dict[str, Any] = {"available": False}

        if forecast:
            times = (forecast.get("hourly") or {}).get("time") or []
            index = _nearest_index(times, target_epoch)
            if index is not None:
                code = _value_at(forecast, "weather_code", index)
                result.update(
                    available=True,
                    observed_for=datetime.fromtimestamp(times[index], tz=timezone.utc).isoformat(),
                    temperature_c=_value_at(forecast, "temperature_2m", index),
                    precipitation_probability=_value_at(forecast, "precipitation_probability", index),
                    weather_code=code,
                    summary=WMO_SUMMARY.get(code) if code is not None else None,
                    wind_speed_kmh=_value_at(forecast, "wind_speed_10m", index),
                )

        if air:
            times = (air.get("hourly") or {}).get("time") or []
            index = _nearest_index(times, target_epoch)
            if index is not None:
                aqi = _value_at(air, "us_aqi", index)
                if aqi is not None:
                    result.update(available=True, us_aqi=int(aqi), aqi_band=_aqi_band(int(aqi)))

        return result

    payload = await cached_json(
        redis,
        geo_key("cond", lat, lng, hour_bucket),
        CACHE_TTL_SECONDS,
        load,
        # An empty result here means both feeds failed, not that there's no
        # weather — don't hold onto that for the full TTL.
        should_cache=lambda value: bool(value.get("available")),
    )
    return ConditionsResponse(**payload)
