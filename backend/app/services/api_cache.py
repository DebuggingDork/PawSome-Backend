"""TTL cache for third-party API responses, backed by the same Redis we already
run for rate limiting and block lookups.

The win here is sharing across *users*, not just across requests from one user.
Every owner looking at a playdate in the same park at the same hour wants the
identical forecast, and every event in a neighbourhood resolves to the same set
of nearby dog parks — so one upstream call can serve all of them. That keeps us
comfortably inside the free tiers' fair-use limits rather than scaling our
external call volume with our user count.

Follows `block_cache.py`'s plain GET/SET-with-TTL shape; the repo uses no cache
framework and this isn't the place to introduce one.
"""

import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


async def cached_json(
    redis,
    key: str,
    ttl_seconds: int,
    loader: Callable[[], Awaitable[Any]],
    should_cache: Callable[[Any], bool] | None = None,
) -> Any:
    """Return `key` from Redis, else `await loader()` and cache the result.

    `should_cache` guards against pinning a bad answer. Loaders here degrade
    rather than raise when a provider is down, so without it a single upstream
    blip would be cached as an empty result and served for the whole TTL —
    turning a momentary outage into a half-hour one.

    Redis being down must never take a feature down with it: a cache is an
    optimisation, and every caller here has a live upstream to fall back on. So
    both the read and the write are best-effort, and a failure on either just
    means we do the uncached thing.
    """
    try:
        hit = await redis.get(key)
        if hit is not None:
            return json.loads(hit)
    except Exception:  # noqa: BLE001 — see docstring
        logger.warning("cache read failed for %s; falling through to upstream", key)

    value = await loader()

    if should_cache is not None and not should_cache(value):
        return value

    try:
        await redis.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:  # noqa: BLE001
        logger.warning("cache write failed for %s", key)

    return value


def geo_key(prefix: str, lat: float, lng: float, *parts: object) -> str:
    """Cache key rounded to ~1.1 km (2 decimal places).

    Coordinates come from a geocoder and are precise to the metre, which would
    make every key unique and the cache useless. Rounding is what actually
    creates the sharing: "the weather at this park" is the same answer for
    anyone within a block of it.
    """
    suffix = ":".join(str(p) for p in parts)
    base = f"{prefix}:{lat:.2f}:{lng:.2f}"
    return f"{base}:{suffix}" if suffix else base
