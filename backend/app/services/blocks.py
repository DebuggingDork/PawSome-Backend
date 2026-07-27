"""Who a user should not be shown.

Blocks existed as rows and as a Redis cache used by the chat paths, but nothing
consulted them when deciding what to *show*: both browse surfaces listed the
pets of people you had blocked, and of people who had blocked you. Blocking
someone and then meeting them again at the top of Discover is the one outcome
a block has to prevent.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block


async def get_blocked_user_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Every user id that must stay hidden from `user_id`, in both directions.

    Symmetric on purpose. A block hides you from them as well as them from you —
    otherwise the person who was blocked keeps seeing and swiping on someone who
    has explicitly opted out of contact with them.
    """
    result = await db.execute(
        select(Block.blocking_user_id, Block.blocked_user_id).where(
            or_(Block.blocking_user_id == user_id, Block.blocked_user_id == user_id)
        )
    )

    blocked: set[uuid.UUID] = set()
    for blocking_user_id, blocked_user_id in result.all():
        blocked.add(blocked_user_id if blocking_user_id == user_id else blocking_user_id)
    blocked.discard(user_id)
    return blocked
