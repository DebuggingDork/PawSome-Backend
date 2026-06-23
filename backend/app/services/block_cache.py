"""Block relationship caching service using Redis for fast safety checks"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block

BLOCK_CACHE_TTL = 300  # 5 minutes


def _block_key(blocking_user_id: str, blocked_user_id: str) -> str:
    return f"block:{blocking_user_id}:{blocked_user_id}"


async def is_blocked(
    redis,
    db: AsyncSession,
    blocking_user_id: str,
    blocked_user_id: str,
) -> bool:
    """Check whether a block relationship exists between two users (either direction).

    Checks Redis cache first; falls back to DB on a miss and caches the result.
    Returns True if either user has blocked the other.
    """
    # Check both directional cache keys
    key_a_b = _block_key(blocking_user_id, blocked_user_id)
    key_b_a = _block_key(blocked_user_id, blocking_user_id)

    if await redis.exists(key_a_b) or await redis.exists(key_b_a):
        return True

    # Cache miss — query DB for either direction
    result = await db.execute(
        select(Block).where(
            (
                (Block.blocking_user_id == blocking_user_id)
                & (Block.blocked_user_id == blocked_user_id)
            )
            | (
                (Block.blocking_user_id == blocked_user_id)
                & (Block.blocked_user_id == blocking_user_id)
            )
        )
    )
    block = result.scalar_one_or_none()

    if block is None:
        return False

    # Cache both directions so future checks are fast
    await cache_block(redis, blocking_user_id, blocked_user_id)
    return True


async def cache_block(
    redis,
    blocking_user_id: str,
    blocked_user_id: str,
) -> None:
    """Cache both directional block keys with a 5-minute TTL."""
    await redis.set(_block_key(blocking_user_id, blocked_user_id), "1", ex=BLOCK_CACHE_TTL)
    await redis.set(_block_key(blocked_user_id, blocking_user_id), "1", ex=BLOCK_CACHE_TTL)


async def invalidate_block_cache(
    redis,
    user_id_a: str,
    user_id_b: str,
) -> None:
    """Remove both directional block cache keys for a pair of users."""
    await redis.delete(
        _block_key(user_id_a, user_id_b),
        _block_key(user_id_b, user_id_a),
    )
