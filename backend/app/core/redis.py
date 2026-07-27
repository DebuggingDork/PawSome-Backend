import logging

from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: Redis = from_url(
    settings.redis_url,
    decode_responses=True,
)

# Separate client for pub/sub subscribers, and it has to be separate.
#
# redis-py defaults `socket_timeout` to 5s, which is right for commands and
# catastrophic for a subscriber: `pubsub.listen()` blocks waiting for the next
# message, so on any conversation quieter than one message every five seconds
# the read timed out, the connection was dropped, and the listener resubscribed
# a second later — a permanent 5s-up/1s-down cycle against Redis. Pub/sub has no
# persistence, so every message and notification published by another worker
# during those gaps was lost outright, which is exactly what "he can send but I
# never receive it" looks like. The old listener swallowed the timeout with a
# bare `except Exception`, so none of this left a trace.
#
# socket_timeout=None lets the subscriber block indefinitely, as it should;
# health_check_interval keeps the connection alive across idle periods.
pubsub_redis_client: Redis = from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=None,
    socket_keepalive=True,
    health_check_interval=30,
)


async def get_redis() -> Redis:
    return redis_client


async def get_pubsub_redis() -> Redis:
    """Client for long-lived subscribers. Use `get_redis` for commands."""
    return pubsub_redis_client


async def check_redis() -> tuple[bool, str | None]:
    """PING Redis and report the result rather than raising.

    Redis backs rate limiting and the cross-worker fan-out for chat and
    notification sockets, so when it is down the visible symptom is a swipe or a
    message quietly not working. Nothing checked it at startup, which left that
    diagnosis to guesswork; the caller logs the outcome either way.

    Returns (ok, error) — `error` is the failure string when ok is False.
    """
    try:
        await redis_client.ping()
        return True, None
    except Exception as exc:  # noqa: BLE001 — any failure here means "unavailable"
        return False, f"{type(exc).__name__}: {exc}"
