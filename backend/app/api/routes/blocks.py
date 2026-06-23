import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import block_rate_limit
from app.core.redis import get_redis
from app.models.block import Block
from app.models.match import Match
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.block import (
    BlockListItemResponse,
    BlockListResponse,
    BlockResponse,
    BlockedUserInfo,
    CreateBlockRequest,
)
from app.services.block_cache import cache_block, invalidate_block_cache

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.post("", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
async def create_block(
    body: CreateBlockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(block_rate_limit),
    redis: Redis = Depends(get_redis),
):
    """
    Block a user.

    - Prevents mutual discovery in browse and hides shared matches.
    - Soft-deletes all active matches between the two users.
    - Caches the block relationship in Redis for fast safety checks.
    """

    # 1. Cannot block yourself
    if body.blocked_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block yourself",
        )

    # 2. Verify blocked user exists
    target_result = await db.execute(
        select(User).where(User.id == body.blocked_user_id)
    )
    target_user = target_result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # 3. Check for an existing block
    existing_block_result = await db.execute(
        select(Block).where(
            Block.blocking_user_id == current_user.id,
            Block.blocked_user_id == body.blocked_user_id,
        )
    )
    if existing_block_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already blocked",
        )

    # 4. Find and soft-delete all active matches between the two users
    # Get pet IDs for both users
    user1_pets_result = await db.execute(
        select(PetProfile.id).where(PetProfile.user_id == current_user.id)
    )
    user1_pet_ids = [row[0] for row in user1_pets_result.all()]

    user2_pets_result = await db.execute(
        select(PetProfile.id).where(PetProfile.user_id == body.blocked_user_id)
    )
    user2_pet_ids = [row[0] for row in user2_pets_result.all()]

    matches_to_delete: list[Match] = []
    if user1_pet_ids and user2_pet_ids:
        matches_result = await db.execute(
            select(Match).where(
                Match.deleted_at.is_(None),
                or_(
                    and_(
                        Match.pet1_id.in_(user1_pet_ids),
                        Match.pet2_id.in_(user2_pet_ids),
                    ),
                    and_(
                        Match.pet1_id.in_(user2_pet_ids),
                        Match.pet2_id.in_(user1_pet_ids),
                    ),
                ),
            )
        )
        matches_to_delete = list(matches_result.scalars().all())
        now = datetime.now(timezone.utc)
        for match in matches_to_delete:
            match.deleted_at = now

    # 5. Create the block record
    block = Block(
        blocking_user_id=current_user.id,
        blocked_user_id=body.blocked_user_id,
    )
    db.add(block)

    # 6. Commit everything in one transaction
    await db.commit()
    await db.refresh(block)

    # 7. Cache the block in Redis
    await cache_block(redis, str(current_user.id), str(body.blocked_user_id))

    # 8. Return 201 with affected match count
    return BlockResponse(
        id=block.id,
        blocking_user_id=block.blocking_user_id,
        blocked_user_id=block.blocked_user_id,
        created_at=block.created_at,
        matches_affected=len(matches_to_delete),
    )


@router.get("", response_model=BlockListResponse)
async def list_blocks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all users blocked by the current user.
    """

    # Query all blocks where current_user is the blocker
    blocks_result = await db.execute(
        select(Block).where(Block.blocking_user_id == current_user.id)
    )
    blocks = list(blocks_result.scalars().all())

    if not blocks:
        return BlockListResponse(blocks=[], total=0)

    # Fetch blocked user details in one query
    blocked_user_ids = [b.blocked_user_id for b in blocks]
    users_result = await db.execute(
        select(User).where(User.id.in_(blocked_user_ids))
    )
    users_map: dict[uuid.UUID, User] = {u.id: u for u in users_result.scalars().all()}

    items: list[BlockListItemResponse] = []
    for block in blocks:
        blocked_user = users_map.get(block.blocked_user_id)
        if blocked_user is None:
            continue
        items.append(
            BlockListItemResponse(
                id=block.id,
                created_at=block.created_at,
                blocked_user=BlockedUserInfo(
                    id=blocked_user.id,
                    full_name=blocked_user.full_name,
                    profile_photo_url=blocked_user.profile_photo_url,
                ),
            )
        )

    return BlockListResponse(blocks=items, total=len(items))


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    block_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """
    Remove a block. The unblocked user will become visible again in browse/matches.
    """

    # 1. Find the block
    block_result = await db.execute(
        select(Block).where(Block.id == block_id)
    )
    block = block_result.scalar_one_or_none()
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found",
        )

    # 2. Verify ownership
    if block.blocking_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this block",
        )

    # 3. Hard-delete the block
    blocked_user_id = str(block.blocked_user_id)
    await db.delete(block)
    await db.commit()

    # 4. Invalidate Redis cache
    await invalidate_block_cache(redis, str(current_user.id), blocked_user_id)
