import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.config import settings
from app.core.database import get_db
from app.models.match import Match
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.auth import (
    UserFullProfile,
    UserPrivateProfile,
    UserProfileUpdate,
    UserPublicProfile,
    ProfileCompletionStatus,
    UserPhotoPresignRequest,
    UserPhotoPresignResponse,
    UserPhotoConfirmRequest,
)
from app.services import r2

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


@router.get("/me/completion", response_model=ProfileCompletionStatus)
async def get_profile_completion(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get profile completion status with gamified progress tracking.
    Helps guide users through onboarding and encourages complete profiles."""
    
    # Check profile fields
    has_profile_photo = user.profile_photo_url is not None and user.profile_photo_url.strip() != ""
    has_full_name = user.full_name is not None and user.full_name.strip() != ""
    has_occupation = user.occupation is not None and user.occupation.strip() != ""
    has_bio = user.bio is not None and user.bio.strip() != ""
    has_address = user.address is not None and user.address.strip() != ""
    
    # Count completed profile fields
    profile_fields = [has_profile_photo, has_full_name, has_occupation, has_bio, has_address]
    profile_completed = sum(profile_fields)
    profile_fields_percentage = (profile_completed / len(profile_fields)) * 100
    
    # Check pets
    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.user_id == user.id)
    )
    pets = pets_result.scalars().all()
    total_pets = len(pets)
    active_pets = sum(1 for p in pets if p.is_active)
    
    has_at_least_one_pet = total_pets > 0
    has_active_pet = active_pets > 0
    
    # Pet profile completion (50% for creating, 50% for activating with photo)
    if total_pets == 0:
        pet_profile_percentage = 0
    elif not has_active_pet:
        pet_profile_percentage = 50
    else:
        pet_profile_percentage = 100
    
    # Overall completion (60% profile, 40% pet)
    overall_percentage = int((profile_fields_percentage * 0.6) + (pet_profile_percentage * 0.4))
    
    # Track completed and missing fields
    completed_fields = []
    missing_fields = []
    
    if has_profile_photo:
        completed_fields.append("profile_photo")
    else:
        missing_fields.append("profile_photo")
    
    if has_full_name:
        completed_fields.append("full_name")
    else:
        missing_fields.append("full_name")
    
    if has_occupation:
        completed_fields.append("occupation")
    else:
        missing_fields.append("occupation")
    
    if has_bio:
        completed_fields.append("bio")
    else:
        missing_fields.append("bio")
    
    if has_address:
        completed_fields.append("address")
    else:
        missing_fields.append("address")
    
    if has_at_least_one_pet:
        completed_fields.append("pet_created")
    else:
        missing_fields.append("pet_created")
    
    if has_active_pet:
        completed_fields.append("pet_photo")
    else:
        missing_fields.append("pet_photo")
    
    # Generate friendly suggestions
    suggestions = []
    if not has_full_name:
        suggestions.append("Add your name so pet owners know who you are")
    if not has_profile_photo:
        suggestions.append("Upload a profile photo to build trust")
    if not has_occupation:
        suggestions.append("Share your occupation to help others get to know you")
    if not has_bio:
        suggestions.append("Write a bio about yourself and your pet preferences")
    if not has_at_least_one_pet:
        suggestions.append("Create your first pet profile to start matching")
    elif not has_active_pet:
        suggestions.append("Upload at least one photo of your pet to activate their profile")
    if not has_address and has_active_pet:
        suggestions.append("Add your address (only visible to matches) for meetups")
    
    if not suggestions:
        suggestions.append("🎉 Your profile is complete! Start swiping to find matches")
    
    # Determine if profile is "complete" (basic threshold)
    has_basic_info = has_full_name and has_occupation
    is_complete = has_basic_info and has_active_pet and has_profile_photo
    
    return ProfileCompletionStatus(
        completion_percentage=overall_percentage,
        is_complete=is_complete,
        completed_fields=completed_fields,
        missing_fields=missing_fields,
        suggestions=suggestions,
        profile_fields_complete=int(profile_fields_percentage),
        pet_profile_complete=int(pet_profile_percentage),
        total_pets=total_pets,
        active_pets=active_pets,
        has_profile_photo=has_profile_photo,
        has_basic_info=has_basic_info,
        has_bio=has_bio,
        has_address=has_address,
        has_at_least_one_pet=has_at_least_one_pet,
        has_active_pet=has_active_pet,
    )


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
    
    # Track which achievements to grant
    from app.models.user_achievement import AchievementType
    from app.services import achievements
    
    grant_achievements = []
    
    # Check if full_name was just added
    if 'full_name' in updates and updates['full_name'] and not user.full_name:
        grant_achievements.append(AchievementType.FULL_NAME)
    
    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    
    # Grant achievements
    for achievement_type in grant_achievements:
        await achievements.grant_achievement(db, user.id, achievement_type)
    
    # Check if profile is now complete and grant achievement
    has_all_fields = all([
        user.full_name,
        user.occupation,
        user.bio,
        user.profile_photo_url,
    ])
    
    # Check if user has at least one active pet
    pets_result = await db.execute(
        select(PetProfile).where(
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
    )
    has_active_pet = pets_result.scalar_one_or_none() is not None
    
    if has_all_fields and has_active_pet:
        await achievements.grant_achievement(db, user.id, AchievementType.PROFILE_COMPLETE)

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


def _require_r2_configured() -> None:
    if not settings.r2_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured",
        )


@router.post("/me/photo/presign", response_model=UserPhotoPresignResponse)
async def presign_profile_photo_upload(
    body: UserPhotoPresignRequest,
    user: User = Depends(get_current_user),
):
    """Get presigned URL to upload profile photo directly to R2"""
    _require_r2_configured()

    object_key = r2.build_user_photo_key(user.id, body.content_type)
    upload_url = r2.create_presigned_upload(object_key, body.content_type)

    return UserPhotoPresignResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=r2.PRESIGNED_URL_EXPIRES_SECONDS,
    )


@router.post("/me/photo", response_model=UserFullProfile)
async def confirm_profile_photo_upload(
    body: UserPhotoConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm profile photo upload and update user profile"""
    _require_r2_configured()

    # Verify object key belongs to this user
    if not body.object_key.startswith(f"users/{user.id}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object key does not belong to this user",
        )

    # Verify file exists and check size
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

    # Track if this is first photo
    is_first_photo = not user.profile_photo_url

    # Delete old photo if exists
    if user.profile_photo_url:
        old_key = user.profile_photo_url.replace(settings.r2_public_base_url.rstrip('/') + '/', '')
        if old_key.startswith(f"users/{user.id}/"):
            await run_in_threadpool(r2.delete_object, old_key)

    # Update user profile
    user.profile_photo_url = r2.public_url(body.object_key)
    await db.commit()
    await db.refresh(user)

    # Grant achievement for first photo upload
    if is_first_photo:
        from app.models.user_achievement import AchievementType
        from app.services import achievements
        await achievements.grant_achievement(db, user.id, AchievementType.PROFILE_PHOTO)

    return UserFullProfile.model_validate(user)


@router.delete("/me/photo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_photo(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete profile photo"""
    _require_r2_configured()

    if not user.profile_photo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile photo to delete",
        )

    # Extract object key and delete from R2
    object_key = user.profile_photo_url.replace(settings.r2_public_base_url.rstrip('/') + '/', '')
    if object_key.startswith(f"users/{user.id}/"):
        await run_in_threadpool(r2.delete_object, object_key)

    # Clear from database
    user.profile_photo_url = None
    await db.commit()
