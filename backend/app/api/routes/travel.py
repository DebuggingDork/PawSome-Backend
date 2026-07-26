"""How far away a place is, and how long it takes to get there.

Two levels of answer, because one of them costs nothing:

- **Straight-line** (always available): haversine over the coordinates we already
  store. Answers "is this even in my city?", which is the question most people
  are actually asking.
- **Routed** (when an Ola Maps key is configured): real road distance and drive
  time. Ola's free tier is 500K calls/month and its India coverage is why it was
  picked over the alternatives.

The routed path is strictly an upgrade — if the key is missing *or* the call
fails for any reason, we return the straight-line answer instead of an error.
A distance label is decorative; it must never be the reason a card breaks.
"""

import httpx
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis

from app.api.deps import get_current_user_optional
from app.core.config import settings
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.travel import TravelEstimate
from app.services.api_cache import cached_json
from app.services.external_http import UpstreamUnavailable, fetch_json
from app.utils.distance import haversine_distance

router = APIRouter(prefix="/travel", tags=["travel"])

CACHE_TTL_SECONDS = 6 * 60 * 60


def _straight_line(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> dict:
    return {
        "distance_km": round(haversine_distance(from_lat, from_lng, to_lat, to_lng), 1),
        "duration_minutes": None,
        "source": "straight_line",
    }


def _parse_ola(payload: dict) -> dict | None:
    """Pull distance/duration out of a Distance Matrix response.

    Ola's routing responses follow the Google Distance Matrix shape, but this is
    written against a provider we can't currently exercise (no key yet), so it
    accepts both the nested `{value: n}` form and a plain number, and returns
    None rather than raising on anything it doesn't recognise. The caller treats
    None exactly like a network failure — fall back to straight-line.
    """
    try:
        element = payload["rows"][0]["elements"][0]
    except (KeyError, IndexError, TypeError):
        return None

    def scalar(field: str) -> float | None:
        raw = element.get(field)
        if isinstance(raw, dict):
            raw = raw.get("value")
        return float(raw) if isinstance(raw, (int, float)) else None

    metres, seconds = scalar("distance"), scalar("duration")
    if metres is None:
        return None

    return {
        "distance_km": round(metres / 1000, 1),
        "duration_minutes": round(seconds / 60) if seconds is not None else None,
        "source": "ola",
    }


async def _routed(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> dict | None:
    if not settings.ola_maps_configured:
        return None

    params = {
        "origins": f"{from_lat},{from_lng}",
        "destinations": f"{to_lat},{to_lng}",
        "api_key": settings.ola_maps_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            payload = await fetch_json(
                client,
                f"{settings.ola_maps_base_url.rstrip('/')}/routing/v1/distanceMatrix",
                params=params,
            )
    except UpstreamUnavailable:
        return None

    return _parse_ola(payload) if isinstance(payload, dict) else None


@router.get("/eta", response_model=TravelEstimate)
async def travel_estimate(
    from_lat: float = Query(..., ge=-90, le=90),
    from_lng: float = Query(..., ge=-180, le=180),
    to_lat: float = Query(..., ge=-90, le=90),
    to_lng: float = Query(..., ge=-180, le=180),
    redis: Redis = Depends(get_redis),
    user: User | None = Depends(get_current_user_optional),
) -> TravelEstimate:
    """Distance (and drive time, where available) between two points.

    Optional auth, because event cards are browsable signed out.
    """

    async def load() -> dict:
        return await _routed(from_lat, from_lng, to_lat, to_lng) or _straight_line(
            from_lat, from_lng, to_lat, to_lng
        )

    # Rounded to ~1.1 km on both ends: everyone setting off from the same
    # neighbourhood to the same park gets one cached answer.
    key = f"eta:{from_lat:.2f}:{from_lng:.2f}:{to_lat:.2f}:{to_lng:.2f}"

    payload = await cached_json(
        redis,
        key,
        CACHE_TTL_SECONDS,
        load,
        # Don't spend six hours serving a straight-line answer we only fell back
        # to because Ola happened to be down for one request.
        should_cache=lambda value: value["source"] == "ola" or not settings.ola_maps_configured,
    )
    return TravelEstimate(**payload)
