"""
Redis-backed rate limiting for PawMeet API endpoints.

Provides a standalone coroutine (`check_rate_limit`) and a FastAPI dependency
factory (`rate_limiter`) that together implement the sliding-counter pattern
described in Requirements 12.1–12.7.

Counter lifecycle
-----------------
1. INCR the key → returns new counter value.
2. If counter == 1 (first increment in window), set EXPIRE to `window` seconds.
   This guarantees automatic TTL even if the process dies after INCR.
3. If counter > `limit`, raise HTTP 429 with Retry-After header.

Requirements covered: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7
"""

import logging
from typing import Callable

from fastapi import Depends, HTTPException
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.models.user import User
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)


async def check_rate_limit(
    redis: Redis,
    user_id: str,
    key_prefix: str,
    limit: int,
    window: int,
) -> None:
    """Increment the request counter and raise HTTP 429 when the limit is exceeded.

    Args:
        redis:      An active async Redis client.
        user_id:    Unique identifier of the acting user (used in the Redis key).
        key_prefix: Logical grouping for the counter, e.g. ``"undo"``, ``"report"``.
        limit:      Maximum number of requests allowed within *window* seconds.
        window:     Length of the rate-limit window in seconds.

    Raises:
        HTTPException: 429 Too Many Requests when ``counter > limit``.

    Redis key format:
        ``rate_limit:{key_prefix}:{user_id}``
    """
    key = f"rate_limit:{key_prefix}:{user_id}"

    # Atomically increment; returns the new value.
    count: int = await redis.incr(key)

    # Set TTL only on the first increment so the window starts fresh each period.
    if count == 1:
        await redis.expire(key, window)

    if count > limit:
        # Requirement 12.7 — log violations for security monitoring.
        logger.warning("Rate limit exceeded: key=%s, user_id=%s", key, user_id)

        # Requirement 12.5 — HTTP 429 with descriptive message and Retry-After header.
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. "
                f"Limit: {limit} requests per {window} seconds."
            ),
            headers={"Retry-After": str(window)},
        )


def rate_limiter(
    key_prefix: str,
    limit: int,
    window: int,
) -> Callable:
    """Factory that returns a FastAPI dependency enforcing the given rate limit.

    Inject the returned callable via ``Depends()`` on any route that needs
    rate limiting.  The dependency resolves the current user and Redis client
    automatically, then delegates to :func:`check_rate_limit`.

    Args:
        key_prefix: Logical name for this limit (e.g. ``"undo"``, ``"block"``).
        limit:      Maximum requests allowed within *window* seconds.
        window:     Length of the rate-limit window in seconds.

    Returns:
        An async FastAPI dependency that raises HTTP 429 when the limit is hit.

    Example::

        undo_rate_limit = rate_limiter("undo", limit=10, window=3600)

        @router.post("/undo-swipe")
        async def undo_swipe(
            _: None = Depends(undo_rate_limit),
            current_user: User = Depends(get_current_user),
        ):
            ...
    """

    async def _dependency(
        current_user: User = Depends(get_current_user),
        redis: Redis = Depends(get_redis),
    ) -> None:
        await check_rate_limit(
            redis=redis,
            user_id=str(current_user.id),
            key_prefix=key_prefix,
            limit=limit,
            window=window,
        )

    return _dependency


# ---------------------------------------------------------------------------
# Pre-built limiters matching the requirements (Req. 12.1–12.4)
# ---------------------------------------------------------------------------

# Requirement 12.1 — 10 undo attempts per hour (3600 s)
undo_rate_limit = rate_limiter("undo", limit=10, window=3600)

# Requirement 12.2 — 5 reports per day (86400 s)
report_rate_limit = rate_limiter("report", limit=5, window=86400)

# Requirement 12.3 — 20 blocks per day (86400 s)
block_rate_limit = rate_limiter("block", limit=20, window=86400)

# Requirement 12.4 — 100 favorites per day (86400 s)
favorite_rate_limit = rate_limiter("favorite", limit=100, window=86400)
