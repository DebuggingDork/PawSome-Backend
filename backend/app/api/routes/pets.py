import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, get_owned_pet
from app.core.database import get_db
from app.models.pet_profile import PetProfile, PetSpecies
from app.models.user import User
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
    db: AsyncSession = Depends(get_db),
):
    """Public catalog of all active pets — no account needed, like browsing
    products in a store. Coordinates are never exposed here. Each item carries
    primary_photo_url for the card image; `total` lets the frontend paginate."""
    filters = [PetProfile.is_active.is_(True)]

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
        .where(*filters)
        .order_by(PetProfile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return PetListResponse(
        items=[PetPublicResponse.model_validate(p) for p in result.scalars().all()],
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
        is_active=False,  # Start as inactive, will be activated after first photo
        **body.model_dump(),
    )
    db.add(pet)
    await db.commit()
    await db.refresh(pet)

    return pet


@router.get("/me", response_model=list[PetResponse])
async def list_my_pets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's active pets. An empty list means onboarding was skipped."""
    result = await db.execute(
        select(PetProfile)
        .where(
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
        .order_by(PetProfile.created_at)
    )
    return result.scalars().all()


@router.get("/{pet_id}", response_model=PetResponse | PetPublicResponse)
async def get_pet(
    pet_id: uuid.UUID,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """View any active pet — public, no account needed (like a product detail
    page). The owner, when logged in, gets full data including coordinates;
    everyone else gets the public view."""
    result = await db.execute(
        select(PetProfile).where(
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
        return PetResponse.model_validate(pet)
    return PetPublicResponse.model_validate(pet)


@router.patch("/{pet_id}", response_model=PetResponse)
async def update_pet(
    body: PetUpdate,
    pet: PetProfile = Depends(get_owned_pet),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(pet, field, value)

    await db.commit()
    await db.refresh(pet)

    return pet


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    pet: PetProfile = Depends(get_owned_pet),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete — deactivates the pet so future swipes/matches keep their references."""
    pet.is_active = False
    await db.commit()
