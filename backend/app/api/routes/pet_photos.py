import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_pet
from app.core.config import settings
from app.core.database import get_db
from app.models.pet_photo import PetPhoto
from app.models.pet_profile import PetProfile
from app.schemas.pet import (
    PetPhotoResponse,
    PhotoConfirmRequest,
    PhotoPresignRequest,
    PhotoPresignResponse,
)
from app.services import r2

MAX_PHOTOS_PER_PET = 5

router = APIRouter(
    prefix="/pets/{pet_id}/photos",
    tags=["pet photos"],
)


def _require_r2_configured() -> None:
    if not settings.r2_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured (missing R2 settings)",
        )


async def _photo_count(db: AsyncSession, pet_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(PetPhoto).where(PetPhoto.pet_id == pet_id)
    )
    return result.scalar_one()


async def _get_owned_photo(
    photo_id: uuid.UUID,
    pet: PetProfile,
    db: AsyncSession,
) -> PetPhoto:
    result = await db.execute(
        select(PetPhoto).where(
            PetPhoto.id == photo_id,
            PetPhoto.pet_id == pet.id,
        )
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )
    return photo


@router.post("/presign", response_model=PhotoPresignResponse)
async def presign_photo_upload(
    body: PhotoPresignRequest,
    pet: PetProfile = Depends(get_owned_pet),
    db: AsyncSession = Depends(get_db),
):
    """Step 1 of upload: get a short-lived URL to PUT the image directly to R2.
    The image bytes never pass through this API."""
    _require_r2_configured()

    if await _photo_count(db, pet.id) >= MAX_PHOTOS_PER_PET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_PHOTOS_PER_PET} photos per pet",
        )

    object_key = r2.build_object_key(pet.id, body.content_type)
    upload_url = r2.create_presigned_upload(object_key, body.content_type)

    return PhotoPresignResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=r2.PRESIGNED_URL_EXPIRES_SECONDS,
    )


@router.post("", response_model=PetPhotoResponse, status_code=status.HTTP_201_CREATED)
async def confirm_photo_upload(
    body: PhotoConfirmRequest,
    pet: PetProfile = Depends(get_owned_pet),
    db: AsyncSession = Depends(get_db),
):
    """Step 2 of upload: after PUTting the file, confirm it so it's saved
    and served. The first photo automatically becomes the primary one and activates the pet."""
    _require_r2_configured()

    # The key embeds the pet id, so one owner can't claim another pet's upload.
    if not body.object_key.startswith(f"pets/{pet.id}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object key does not belong to this pet",
        )

    existing = await db.execute(
        select(PetPhoto).where(PetPhoto.object_key == body.object_key)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Photo already confirmed",
        )

    count = await _photo_count(db, pet.id)
    if count >= MAX_PHOTOS_PER_PET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_PHOTOS_PER_PET} photos per pet",
        )

    size = await run_in_threadpool(r2.get_object_size, body.object_key)
    if size is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload not found in storage — PUT the file first",
        )
    if size > r2.MAX_PHOTO_BYTES:
        await run_in_threadpool(r2.delete_object, body.object_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image exceeds {r2.MAX_PHOTO_BYTES // (1024 * 1024)} MB limit",
        )

    is_first_photo = (count == 0)
    
    photo = PetPhoto(
        pet_id=pet.id,
        object_key=body.object_key,
        url=r2.public_url(body.object_key),
        is_primary=is_first_photo,
        sort_order=count,
    )
    db.add(photo)
    
    # Activate pet when first photo is uploaded
    if is_first_photo and not pet.is_active:
        pet.is_active = True
    
    await db.commit()
    await db.refresh(photo)

    return photo


@router.patch("/{photo_id}/primary", response_model=PetPhotoResponse)
async def set_primary_photo(
    photo_id: uuid.UUID,
    pet: PetProfile = Depends(get_owned_pet),
    db: AsyncSession = Depends(get_db),
):
    """Make this photo the card image shown in the browse catalog."""
    photo = await _get_owned_photo(photo_id, pet, db)

    for p in pet.photos:
        p.is_primary = p.id == photo.id

    await db.commit()
    await db.refresh(photo)

    return photo


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: uuid.UUID,
    pet: PetProfile = Depends(get_owned_pet),
    db: AsyncSession = Depends(get_db),
):
    """Remove the photo from storage and the profile. If it was the primary,
    the oldest remaining photo is promoted. Cannot delete the last photo - pets require at least one image."""
    _require_r2_configured()

    photo = await _get_owned_photo(photo_id, pet, db)
    
    # Check if this is the last photo
    current_count = await _photo_count(db, pet.id)
    if current_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last photo. Pets must have at least one image.",
        )
    
    was_primary = photo.is_primary
    object_key = photo.object_key

    await db.delete(photo)
    await db.flush()

    if was_primary:
        result = await db.execute(
            select(PetPhoto)
            .where(PetPhoto.pet_id == pet.id)
            .order_by(PetPhoto.sort_order)
            .limit(1)
        )
        next_photo = result.scalar_one_or_none()
        if next_photo is not None:
            next_photo.is_primary = True

    await db.commit()
    await run_in_threadpool(r2.delete_object, object_key)
