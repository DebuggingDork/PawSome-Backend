"""Nearby dog parks, parks, and vets, from OpenStreetMap via the Overpass API.

Most playdates happen at one of a handful of obvious local spots, so offering
those directly beats making everyone type a full address — the same reasoning
behind the quick date slots in the propose form.

Overpass is free and keyless. Its fair-use guidance is roughly 10k queries and
1 GB per day for the public instance, which a 24-hour cache keeps us far inside:
points of interest barely change, so one query per neighbourhood per day serves
everyone in it.
"""

import logging

import httpx
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis

from app.api.deps import get_current_user
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.places import NearbyPlace, NearbyPlaceList, PlaceKind
from app.services.api_cache import cached_json, geo_key
from app.services.external_http import (
    Throttle,
    UpstreamUnavailable,
    fetch_json,
    unavailable,
)
from app.utils.distance import haversine_distance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["places"])

# Overpass is volunteer-run and does real computation per query, so under load
# it sheds requests with a 429 or 504 rather than queueing them — this failed
# roughly one run in two during development. Both entries here are established
# public instances of the same API; falling through to the second on failure
# turns a common transient error into a slightly slower success. They're tried
# in order, so the main instance still takes the normal traffic.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

# OSM tags behind each kind we expose. Keeping our vocabulary separate from
# OSM's means the API doesn't leak tagging conventions we don't control.
KIND_TAGS: dict[str, tuple[str, str]] = {
    "dog_park": ("leisure", "dog_park"),
    "park": ("leisure", "park"),
    "vet": ("amenity", "veterinary"),
}

DEFAULT_KINDS = "dog_park,park,vet"
MAX_RESULTS = 40
CACHE_TTL_SECONDS = 24 * 60 * 60

# Overpass is a volunteer-run service doing real computation per query. One
# request every two seconds across the whole backend is well inside what they
# ask for, and the 24h cache means we rarely queue at all.
_throttle = Throttle(2.0)


def _build_query(lat: float, lng: float, radius_m: int, kinds: list[str]) -> str:
    """Overpass QL for every requested kind within the radius.

    Both `node` and `way` are matched because parks are usually mapped as areas,
    not points — querying nodes alone finds almost nothing. `out center` then
    gives each way a representative coordinate so everything comes back in the
    same shape.
    """
    clauses = []
    for kind in kinds:
        key, value = KIND_TAGS[kind]
        for element in ("node", "way"):
            clauses.append(f'{element}["{key}"="{value}"](around:{radius_m},{lat},{lng});')

    return f"[out:json][timeout:25];({''.join(clauses)});out center {MAX_RESULTS};"


def _kind_of(tags: dict) -> PlaceKind | None:
    for kind, (key, value) in KIND_TAGS.items():
        if tags.get(key) == value:
            return kind  # type: ignore[return-value]
    return None


def _to_place(element: dict, lat: float, lng: float) -> dict | None:
    tags = element.get("tags") or {}
    name = (tags.get("name") or "").strip()
    # An unnamed polygon is useless as a suggestion chip — nobody can agree to
    # meet at "way/38472911".
    if not name:
        return None

    kind = _kind_of(tags)
    if kind is None:
        return None

    # Nodes carry lat/lon directly; ways get theirs from `out center`.
    center = element.get("center") or element
    place_lat, place_lng = center.get("lat"), center.get("lon")
    if place_lat is None or place_lng is None:
        return None

    return {
        "name": name,
        "kind": kind,
        "latitude": place_lat,
        "longitude": place_lng,
        "distance_m": round(haversine_distance(lat, lng, place_lat, place_lng) * 1000),
    }


@router.get("/nearby", response_model=NearbyPlaceList)
async def nearby_places(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(3000, ge=100, le=20000),
    kinds: str = Query(DEFAULT_KINDS, description="Comma-separated: dog_park, park, vet"),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
) -> NearbyPlaceList:
    """Named dog parks / parks / vets within `radius_m`, nearest first."""
    requested = [k.strip() for k in kinds.split(",") if k.strip() in KIND_TAGS]
    if not requested:
        requested = list(KIND_TAGS)
    requested.sort()  # stable cache key regardless of parameter order

    async def load() -> list[dict]:
        query = _build_query(lat, lng, radius_m, requested)
        payload = None

        async with httpx.AsyncClient(timeout=40.0) as client:
            for url in OVERPASS_URLS:
                async with _throttle:
                    try:
                        payload = await fetch_json(client, url, method="POST", data={"data": query})
                        break
                    except UpstreamUnavailable:
                        logger.warning("Overpass instance %s failed; trying the next", url)

        if payload is None:
            raise UpstreamUnavailable("every Overpass instance failed")

        places = [
            place
            for place in (_to_place(el, lat, lng) for el in payload.get("elements", []))
            if place is not None
        ]
        places.sort(key=lambda p: p["distance_m"])
        return places[:MAX_RESULTS]

    try:
        items = await cached_json(
            redis,
            geo_key("poi", lat, lng, radius_m, "-".join(requested)),
            CACHE_TTL_SECONDS,
            load,
        )
    except UpstreamUnavailable:
        # Unlike weather, there's no partial answer to degrade to — an empty
        # list would read as "no parks near you", which is worse than an error
        # the UI can quietly swallow.
        raise unavailable("Nearby place search")

    return NearbyPlaceList(items=[NearbyPlace(**item) for item in items], total=len(items))
