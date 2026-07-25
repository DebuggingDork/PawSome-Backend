import asyncio
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.geocoding import GeocodeResult

router = APIRouter(prefix="/geocoding", tags=["geocoding"])

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

# Nominatim's public API doesn't send Access-Control-Allow-Origin, so calling it
# directly from the browser gets blocked by CORS (confirmed live - the frontend
# used to call it directly and every search silently hung). Proxying through the
# backend sidesteps that entirely, since server-to-server calls aren't subject to
# CORS, and lets us send a real identifying User-Agent per their usage policy
# instead of hoping a browser's Referer header is good enough.
HEADERS = {"User-Agent": "PawSomeApp/1.0 (dev)"}

# Their usage policy caps this service at ~1 request/second. Every user's request
# comes through this one backend process, so a single shared throttle here keeps
# us under that regardless of how many people are searching at once - each
# request just queues behind the last one instead of racing it.
_throttle_lock = asyncio.Lock()
_last_call_monotonic = 0.0
MIN_INTERVAL_SECONDS = 1.0


class ClientGone(Exception):
    """The browser cancelled this request before it reached the front of the queue."""


async def _throttled_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    request: Request | None = None,
) -> httpx.Response:
    global _last_call_monotonic
    async with _throttle_lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_monotonic)
        if wait > 0:
            await asyncio.sleep(wait)

        # Typing an address produces a burst of searches, each one abandoned by
        # the next keystroke. Aborting the fetch in the browser doesn't stop the
        # handler here, so without this check every dead search still waited its
        # turn and spent a full second of the shared Nominatim budget fetching a
        # result nobody would ever read — delaying the one search that mattered
        # behind all of them.
        if request is not None and await request.is_disconnected():
            raise ClientGone

        try:
            response = await client.get(url, params=params, headers=HEADERS)
        finally:
            _last_call_monotonic = time.monotonic()
    return response


def _to_result(raw: dict) -> GeocodeResult:
    address = raw.get("address") or {}
    return GeocodeResult(
        address=raw.get("display_name", ""),
        pincode=address.get("postcode"),
        lat=float(raw["lat"]),
        lng=float(raw["lon"]),
    )


@router.get("/search", response_model=list[GeocodeResult])
async def search_address(
    request: Request,
    q: str = Query(..., min_length=3, max_length=200),
    user: User = Depends(get_current_user),
):
    """Address autocomplete while typing (debounced client-side)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await _throttled_get(
                client,
                f"{NOMINATIM_BASE}/search",
                {"format": "jsonv2", "addressdetails": 1, "limit": 5, "q": q},
                request,
            )
    except ClientGone:
        # Nobody is waiting on this any more; an empty list is the cheapest way
        # to close it out.
        return []
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Address search is temporarily unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Address search is temporarily unavailable")

    return [_to_result(item) for item in response.json()]


@router.get("/reverse", response_model=GeocodeResult)
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    user: User = Depends(get_current_user),
):
    """Reverse-geocodes coordinates (from "use my current location") into an address + pincode."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await _throttled_get(
                client,
                f"{NOMINATIM_BASE}/reverse",
                {"format": "jsonv2", "addressdetails": 1, "lat": lat, "lon": lng},
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Reverse geocoding is temporarily unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Reverse geocoding is temporarily unavailable")

    data = response.json()
    if "error" in data:
        # No address found at these exact coordinates (e.g. open water) - real,
        # not exceptional; hand back the coordinates with no address rather than
        # erroring the whole request out.
        return GeocodeResult(address="", pincode=None, lat=lat, lng=lng)

    return _to_result(data)
