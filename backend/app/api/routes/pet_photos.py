import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_pet, get_owned_pet_any
from app.api.photo_uploads import read_upload_within_limit, validated_upload_content_type
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
    pet: PetProfile = Depends(get_owned_pet_any),
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
    pet: PetProfile = Depends(get_owned_pet_any),
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

    return await _save_pet_photo(db, pet, body.object_key, count)


async def _save_pet_photo(
    db: AsyncSession,
    pet: PetProfile,
    object_key: str,
    count: int,
) -> PetPhoto:
    """Record an object that is already in R2 as one of this pet's photos.

    Shared by the presigned flow and the proxied one below. Everything from
    here on has to be identical between them — which photo becomes primary,
    when the pet goes active, which achievement fires — because from the
    product's point of view they are the same action.
    """
    is_first_photo = (count == 0)

    photo = PetPhoto(
        pet_id=pet.id,
        object_key=object_key,
        url=r2.public_url(object_key),
        is_primary=is_first_photo,
        sort_order=count,
    )
    db.add(photo)

    # Activate pet when first photo is uploaded
    if is_first_photo and not pet.is_active:
        pet.is_active = True

    await db.commit()
    await db.refresh(photo)

    # Grant achievement for first pet photo
    if is_first_photo:
        from app.models.user_achievement import AchievementType
        from app.services import achievements
        await achievements.grant_achievement(db, pet.user_id, AchievementType.PET_PHOTO)

    return photo


@router.post("/upload", response_model=PetPhotoResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: UploadFile = File(...),
    pet: PetProfile = Depends(get_owned_pet_any),
    db: AsyncSession = Depends(get_db),
):
    """Upload a pet photo through this API instead of straight to R2.

    The fallback for when the browser cannot reach R2 directly — its origin is
    not in the bucket's exactly-matched CORS allowlist, so the PUT never
    leaves the device. See the profile-photo equivalent in routes/users.py and
    put_object in services/r2.py for the full reasoning.
    """
    _require_r2_configured()

    count = await _photo_count(db, pet.id)
    if count >= MAX_PHOTOS_PER_PET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum of {MAX_PHOTOS_PER_PET} photos per pet",
        )

    content_type = validated_upload_content_type(file)
    data = await read_upload_within_limit(file)

    object_key = r2.build_object_key(pet.id, content_type)
    await run_in_threadpool(r2.put_object, object_key, data, content_type)

    return await _save_pet_photo(db, pet, object_key, count)


@router.post("/{photo_id}/replace/presign", response_model=PhotoPresignResponse)
async def presign_photo_replace(
    photo_id: uuid.UUID,
    body: PhotoPresignRequest,
    pet: PetProfile = Depends(get_owned_pet_any),
    db: AsyncSession = Depends(get_db),
):
    """Step 1 of replacing an existing photo's image in place: get a presigned
    URL for the new file. Doesn't touch the DB row or count against the
    5-photo cap — swapping a photo isn't adding one."""
    _require_r2_configured()
    await _get_owned_photo(photo_id, pet, db)

    object_key = r2.build_object_key(pet.id, body.content_type)
    upload_url = r2.create_presigned_upload(object_key, body.content_type)

    return PhotoPresignResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=r2.PRESIGNED_URL_EXPIRES_SECONDS,
    )


@router.post("/{photo_id}/replace", response_model=PetPhotoResponse)
async def confirm_photo_replace(
    photo_id: uuid.UUID,
    body: PhotoConfirmRequest,
    pet: PetProfile = Depends(get_owned_pet_any),
    db: AsyncSession = Depends(get_db),
):
    """Step 2: point this photo at the newly uploaded file, keeping its id,
    is_primary, and sort_order — a delete+re-add would lose the slot's
    position and (if it was primary) its primary status. The old file is
    removed from storage once the swap is saved."""
    _require_r2_configured()
    photo = await _get_owned_photo(photo_id, pet, db)

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

    return await _swap_photo_object(db, photo, body.object_key)


async def _swap_photo_object(db: AsyncSession, photo: PetPhoto, object_key: str) -> PetPhoto:
    """Repoint an existing photo row at a new object, then bin the old file.

    The delete happens after the commit deliberately: if it went first, a
    failed commit would leave the row pointing at a file that no longer exists.
    """
    old_object_key = photo.object_key
    photo.object_key = object_key
    photo.url = r2.public_url(object_key)

    await db.commit()
    await db.refresh(photo)
    if old_object_key != object_key:
        await run_in_threadpool(r2.delete_object, old_object_key)

    return photo


@router.post("/{photo_id}/replace/upload", response_model=PetPhotoResponse)
async def upload_photo_replace(
    photo_id: uuid.UUID,
    file: UploadFile = File(...),
    pet: PetProfile = Depends(get_owned_pet_any),
    db: AsyncSession = Depends(get_db),
):
    """Replace a photo's image, with the bytes routed through this API.

    Same fallback as /upload — see that route for why it exists."""
    _require_r2_configured()
    photo = await _get_owned_photo(photo_id, pet, db)

    content_type = validated_upload_content_type(file)
    data = await read_upload_within_limit(file)

    object_key = r2.build_object_key(pet.id, content_type)
    await run_in_threadpool(r2.put_object, object_key, data, content_type)

    return await _swap_photo_object(db, photo, object_key)


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
