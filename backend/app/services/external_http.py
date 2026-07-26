"""Shared plumbing for calling third-party HTTP APIs.

Every external provider we talk to needs the same three things: an identifying
User-Agent (most free APIs require one), a politeness throttle, and a way to turn
"the vendor is down" into a 502 rather than a 500. `geocoding.py` grew its own
copies of all three first; this module exists so weather, places, and travel
don't grow three more.

`geocoding.py` is deliberately left alone — it's tuned for Nominatim's specific
1 req/s policy and its client-disconnect handling exists for a concrete reason
(abandoned autocomplete keystrokes were eating the whole per-second budget).
Rewriting a working, load-bearing path to share code buys nothing today.
"""

import asyncio
import time
from typing import Any

import httpx
from fastapi import HTTPException, status

# Free APIs (Nominatim, Overpass, Open-Meteo) all ask callers to identify
# themselves so they can contact you before blocking you.
USER_AGENT = "PawSomeApp/1.0 (https://pawsome.app; contact: support@pawsome.app)"

DEFAULT_HEADERS = {"User-Agent": USER_AGENT}


class Throttle:
    """Serialises calls to one provider, holding them at most one per interval.

    Every user's request funnels through this single backend process, so one
    shared throttle per provider keeps us inside their published rate limit
    regardless of how many people are using the app at once — each caller just
    queues behind the last rather than racing it.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def __aenter__(self) -> "Throttle":
        await self._lock.acquire()
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        # Stamp on the way out, not the way in: the next caller should wait an
        # interval from when this request *finished*, otherwise a slow response
        # lets the following one fire immediately.
        self._last_call = time.monotonic()
        self._lock.release()


class UpstreamUnavailable(Exception):
    """A provider errored, timed out, or returned a non-200.

    Raised instead of HTTPException so callers can decide whether the failure is
    fatal (surface a 502) or something to fall back from (e.g. travel/eta drops
    to straight-line distance rather than failing the card).
    """


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
) -> Any:
    """One external call, with transport and status errors collapsed into
    `UpstreamUnavailable`. Returns the decoded JSON body."""
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    try:
        response = await client.request(
            method, url, params=params, data=data, headers=merged_headers
        )
    except httpx.HTTPError as exc:
        raise UpstreamUnavailable(str(exc)) from exc

    if response.status_code != 200:
        raise UpstreamUnavailable(f"{url} returned {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise UpstreamUnavailable(f"{url} returned a non-JSON body") from exc


def unavailable(service: str) -> HTTPException:
    """The 502 we hand back when a provider fails and there's no fallback."""
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"{service} is temporarily unavailable",
    )
