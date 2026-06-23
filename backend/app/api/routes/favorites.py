"""
Favorites management endpoints.

POST   /favorites           — bookmark a target pet (201)
GET    /favorites           — list favorites for a pet (200)
DELETE /favorites/{id}      — soft-delete a favorite (204)

Requirements: 2.1–2.7, 11.2, 11.3, 12.4, 13.1, 13.8
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import favorite_rate_limit
from app.models.favorite import Favorite
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.favorite import (
    CreateFavoriteRequest,
    FavoriteListResponse,
    FavoriteResponse,
    FavoriteWithPetResponse,
)
from app.schemas.pet import PetPublicResponse

router = APIRouter(prefix="/favorites", tags=["favorites"])


# ---------------------------------------------------------------------------
# POST /favorites  →  201 Created
# ---------------------------------------------------------------------------

@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    body: CreateFavoriteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(favorite_rate_limit),
):
    """
    Bookmark a target pet for the current user's pet.

    - 404  if pet_id does not belong to the current user or is inactive
    - 404  if target_pet_id does not exist or is inactive
    - 400  if pet_id == target_pet_id
    - 400  if an active favorite already exists for this pair
    - 201  on success
    """

    # 1. Verify pet_id belongs to current user and is active
    pet_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == body.pet_id,
            PetProfile.user_id == current_user.id,
            PetProfile.is_active.is_(True),
        )
    )
    pet = pet_result.scalar_one_or_none()
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your pet not found or inactive",
        )

    # 2. Verify target_pet_id exists and is active
    target_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == body.target_pet_id,
            PetProfile.is_active.is_(True),
        )
    )
    target_pet = target_result.scalar_one_or_none()
    if target_pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target pet not found or inactive",
        )

    # 3. Prevent self-favoriting
    if body.pet_id == body.target_pet_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot favorite your own pet",
        )

    # 4. Check for existing active favorite
    existing_result = await db.execute(
        select(Favorite).where(
            Favorite.pet_id == body.pet_id,
            Favorite.target_pet_id == body.target_pet_id,
            Favorite.deleted_at.is_(None),
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pet already in favorites",
        )

    # 5. Create the favorite
    # Handle the case where a soft-deleted record exists for the same pair
    # (UniqueConstraint covers pet_id + target_pet_id, so we update rather than insert)
    existing_deleted_result = await db.execute(
        select(Favorite).where(
            Favorite.pet_id == body.pet_id,
            Favorite.target_pet_id == body.target_pet_id,
        )
    )
    existing_deleted = existing_deleted_result.scalar_one_or_none()

    if existing_deleted is not None:
        # Re-activate the soft-deleted record
        existing_deleted.deleted_at = None
        existing_deleted.created_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing_deleted)
        return FavoriteResponse.model_validate(existing_deleted)

    favorite = Favorite(
        pet_id=body.pet_id,
        target_pet_id=body.target_pet_id,
    )
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)

    return FavoriteResponse.model_validate(favorite)


# ---------------------------------------------------------------------------
# GET /favorites  →  200 OK
# ---------------------------------------------------------------------------

@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    pet_id: uuid.UUID = Query(description="Your pet ID to list favorites for"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List active favorites for the given pet, paginated.

    - 403 if pet_id does not belong to the current user
    """

    # 1. Verify ownership (no need for is_active check — allow listing even for
    #    temporarily inactive pets so users retain their saved lists)
    owner_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == pet_id,
            PetProfile.user_id == current_user.id,
        )
    )
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this pet",
        )

    # 2. Total count
    count_result = await db.execute(
        select(func.count())
        .select_from(Favorite)
        .where(
            Favorite.pet_id == pet_id,
            Favorite.deleted_at.is_(None),
        )
    )
    total: int = count_result.scalar_one()

    # 3. Paginated favorites
    favs_result = await db.execute(
        select(Favorite)
        .where(
            Favorite.pet_id == pet_id,
            Favorite.deleted_at.is_(None),
        )
        .order_by(Favorite.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    favorites = favs_result.scalars().all()

    if not favorites:
        return FavoriteListResponse(items=[], total=total, limit=limit, offset=offset)

    # 4. Load target pets and their owners
    target_pet_ids = [f.target_pet_id for f in favorites]

    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_(target_pet_ids))
    )
    pets_map: dict[uuid.UUID, PetProfile] = {p.id: p for p in pets_result.scalars().all()}

    owner_ids = list({p.user_id for p in pets_map.values()})
    users_result = await db.execute(select(User).where(User.id.in_(owner_ids)))
    users_map: dict[uuid.UUID, User] = {u.id: u for u in users_result.scalars().all()}

    # 5. Build response items
    items: list[FavoriteWithPetResponse] = []
    for fav in favorites:
        target_pet = pets_map.get(fav.target_pet_id)
        if target_pet is None:
            continue
        owner = users_map.get(target_pet.user_id)
        pet_dict = PetPublicResponse.model_validate(target_pet).model_dump()
        pet_dict["owner"] = owner
        items.append(
            FavoriteWithPetResponse(
                id=fav.id,
                target_pet=pet_dict,
                created_at=fav.created_at,
            )
        )

    return FavoriteListResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# DELETE /favorites/{favorite_id}  →  204 No Content
# ---------------------------------------------------------------------------

@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    favorite_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-delete a favorite by ID.

    - 404 if favorite not found or already deleted
    - 403 if the favoriting pet does not belong to the current user
    """

    # 1. Fetch active favorite
    fav_result = await db.execute(
        select(Favorite).where(
            Favorite.id == favorite_id,
            Favorite.deleted_at.is_(None),
        )
    )
    favorite = fav_result.scalar_one_or_none()
    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )

    # 2. Verify ownership via the favoriting pet
    pet_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == favorite.pet_id,
            PetProfile.user_id == current_user.id,
        )
    )
    if pet_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own the pet that created this favorite",
        )

    # 3. Soft-delete
    favorite.deleted_at = datetime.now(timezone.utc)
    await db.commit()
