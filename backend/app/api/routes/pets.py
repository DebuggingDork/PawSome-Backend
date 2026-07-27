import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional, get_owned_pet_any
from app.core.database import get_db
from app.models.match import Match
from app.models.pet_profile import PetProfile, PetSpecies
from app.models.user import User
from app.services.blocks import get_blocked_user_ids
from app.schemas.pet import (
    PetCreate,
    PetListResponse,
    PetPublicResponse,
    PetResponse,
    PetUpdate,
)

MAX_PETS_PER_USER = 5

router = APIRouter(
    prefix="/pets",
    tags=["pets"],
)


@router.get("", response_model=PetListResponse)
async def browse_pets(
    species: PetSpecies | None = None,
    gender: Literal["male", "female"] | None = None,
    breed: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Browsable directory of active pets — viewable without an account, like
    the pet's own detail page. Coordinates are never exposed here. Owner info
    (name, occupation, profile photo) is only attached for signed-in requests;
    anonymous visitors see the pet but not who owns it.

    Pets the signed-in caller has already matched with are left out: that
    conversation lives in Matches/Chat now, and leaving them in the directory
    meant being offered "Interested" on a pet you are already talking to."""
    filters = [PetProfile.is_active.is_(True)]

    if user is not None:
        # Blocked in either direction: their pets never appear here again. This
        # is what separates blocking from a plain unmatch, which puts the pair
        # back in each other's decks.
        blocked_user_ids = await get_blocked_user_ids(db, user.id)
        if blocked_user_ids:
            filters.append(PetProfile.user_id.notin_(blocked_user_ids))

        own_pets_result = await db.execute(
            select(PetProfile.id).where(PetProfile.user_id == user.id)
        )
        own_pet_ids = [row[0] for row in own_pets_result.all()]
        if own_pet_ids:
            matched_result = await db.execute(
                select(Match.pet1_id, Match.pet2_id).where(
                    Match.deleted_at.is_(None),
                    or_(
                        Match.pet1_id.in_(own_pet_ids),
                        Match.pet2_id.in_(own_pet_ids),
                    ),
                )
            )
            own = set(own_pet_ids)
            matched_ids = {
                (pet2_id if pet1_id in own else pet1_id)
                for pet1_id, pet2_id in matched_result.all()
            }
            # Guard against a self-match row ever excluding the caller's own pet.
            matched_ids -= own
            if matched_ids:
                filters.append(PetProfile.id.notin_(matched_ids))

    if species is not None:
        filters.append(PetProfile.species == species)
    if gender is not None:
        filters.append(PetProfile.gender == gender)
    if breed is not None:
        filters.append(PetProfile.breed.ilike(f"%{breed}%"))

    total = (
        await db.execute(select(func.count()).select_from(PetProfile).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(PetProfile)
        .options(selectinload(PetProfile.user))
        .where(*filters)
        .order_by(PetProfile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    pets = result.scalars().all()

    items = [PetPublicResponse.model_validate(pet) for pet in pets]
    if user is None:
        for item in items:
            item.owner = None

    return PetListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
async def create_pet(
    body: PetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new pet profile. Note: Pet will be created but should have at least
    one photo uploaded via the photo endpoints before being shown in browse."""
    count_result = await db.execute(
        select(func.count())
        .select_from(PetProfile)
        .where(
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
    )
    if count_result.scalar_one() >= MAX_PETS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_PETS_PER_USER} pets per user",
        )

    pet = PetProfile(
        user_id=user.id,
        is_active= False,  # Start as inactive, will be activated after first photo
        **body.model_dump(),
    )
    db.add(pet)
    await db.commit()
    await db.refresh(pet)

    # Grant achievement for first pet created
    from app.models.user_achievement import AchievementType
    from app.services import achievements
    await achievements.grant_achievement(db, user.id, AchievementType.PET_CREATED)

    # Return pet with owner info (owner property alias returns the user)
    return PetResponse.model_validate(pet)


@router.get("/me", response_model=list[PetResponse])
async def list_my_pets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's pets, active or not. An empty list means onboarding was skipped.
    Includes inactive pets (not yet photographed) since this is the owner's own management view,
    not the public browse catalog."""
    result = await db.execute(
        select(PetProfile)
        .where(PetProfile.user_id == user.id)
        .order_by(PetProfile.created_at)
    )
    pets = result.scalars().all()
    
    # Add owner info to each pet (owner property alias returns the user)
    return [PetResponse.model_validate(pet) for pet in pets]


@router.get("/{pet_id}", response_model=PetResponse | PetPublicResponse)
async def get_pet(
    pet_id: uuid.UUID,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """View any active pet — public, no account needed (like a product detail
    page). The owner, when logged in, gets full data including coordinates;
    everyone else gets the public view with owner info."""
    result = await db.execute(
        select(PetProfile)
        .options(selectinload(PetProfile.user))
        .where(
            PetProfile.id == pet_id,
            PetProfile.is_active.is_(True),
        )
    )
    pet = result.scalar_one_or_none()

    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pet not found",
        )

    if user is not None and pet.user_id == user.id:
        # Owner's view - full data with owner info
        return PetResponse.model_validate(pet)

    # Public view: owner info only for signed-in visitors, never for anonymous ones
    public = PetPublicResponse.model_validate(pet)
    if user is None:
        public.owner = None
    return public


@router.patch("/{pet_id}", response_model=PetResponse)
async def update_pet(
    body: PetUpdate,
    # get_owned_pet (not _any) requires is_active=True — right for browse/swipe,
    # wrong here: a pet stays inactive until its first photo, so that filter
    # 404'd owners trying to fix a typo on their own still-photo-less draft.
    pet: PetProfile = Depends(get_owned_pet_any),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(pet, field, value)

    await db.commit()
    await db.refresh(pet)

    # Return pet with owner info (owner property alias returns the user)
    return PetResponse.model_validate(pet)


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    # Same reasoning as update_pet: must also match still-photo-less drafts,
    # otherwise an abandoned draft could never be removed either.
    pet: PetProfile = Depends(get_owned_pet_any),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete — deactivates the pet so future swipes/matches keep their references."""
    pet.is_active = False
    await db.commit()
