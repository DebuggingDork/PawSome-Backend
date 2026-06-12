import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models.match import Match
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.auth import (
    UserFullProfile,
    UserPrivateProfile,
    UserProfileUpdate,
    UserPublicProfile,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


async def _check_if_matched(db: AsyncSession, current_user_id: uuid.UUID, target_user_id: uuid.UUID) -> bool:
    """Check if current user has any pet matched with any pet of target user."""
    # Get all pets of current user
    current_user_pets_result = await db.execute(
        select(PetProfile.id).where(PetProfile.user_id == current_user_id)
    )
    current_user_pet_ids = [row[0] for row in current_user_pets_result.all()]

    # Get all pets of target user
    target_user_pets_result = await db.execute(
        select(PetProfile.id).where(PetProfile.user_id == target_user_id)
    )
    target_user_pet_ids = [row[0] for row in target_user_pets_result.all()]

    if not current_user_pet_ids or not target_user_pet_ids:
        return False

    # Check if any combination is matched
    for current_pet_id in current_user_pet_ids:
        for target_pet_id in target_user_pet_ids:
            pet1_id, pet2_id = sorted([current_pet_id, target_pet_id])
            match_result = await db.execute(
                select(Match).where(
                    Match.pet1_id == pet1_id,
                    Match.pet2_id == pet2_id,
                )
            )
            if match_result.scalar_one_or_none():
                return True

    return False


@router.get("/me", response_model=UserFullProfile)
async def get_my_profile(user: User = Depends(get_current_user)):
    """Get the authenticated user's full profile including address and email."""
    return UserFullProfile.model_validate(user)


@router.patch("/me", response_model=UserFullProfile)
async def update_my_profile(
    body: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile."""
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return UserFullProfile.model_validate(user)


@router.get("/{user_id}", response_model=UserPublicProfile | UserPrivateProfile)
async def get_user_profile(
    user_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's profile with privacy controls:
    - Public view (no auth needed): name, occupation, bio, profile photo
    - Private view (matched connections only): includes address
    - Not visible: email
    """
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # If the current user is viewing their own profile, redirect to /me
    if current_user and current_user.id == user_id:
        return UserPrivateProfile.model_validate(target_user)

    # Check if they have matched pets
    if current_user:
        is_matched = await _check_if_matched(db, current_user.id, user_id)
        if is_matched:
            # Matched users can see address
            return UserPrivateProfile.model_validate(target_user)

    # Default: public profile only
    return UserPublicProfile.model_validate(target_user)
