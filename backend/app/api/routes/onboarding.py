"""Onboarding wizard endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.onboarding import OnboardingStatus, OnboardingStep, OnboardingStepStatus

router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"],
)


@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current onboarding wizard status with all steps"""
    
    # Check what's completed
    has_verified_email = user.is_verified
    has_basic_profile = bool(user.full_name and user.occupation)
    has_profile_photo = bool(user.profile_photo_url)
    has_bio = bool(user.bio)
    
    # Check pets
    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.user_id == user.id)
    )
    pets = pets_result.scalars().all()
    has_pet = len(pets) > 0
    has_active_pet = any(p.is_active for p in pets)
    
    # Define all steps with their requirements
    steps_config = [
        {
            "step": OnboardingStep.EMAIL_VERIFICATION,
            "title": "Verify Your Email",
            "description": "Check your inbox and click the verification link",
            "completed": has_verified_email,
            "required": False,  # Can skip but recommended
            "action_url": "/api/v1/auth/resend-verification",
            "action_text": "Resend Email",
        },
        {
            "step": OnboardingStep.PROFILE_BASICS,
            "title": "Tell Us About Yourself",
            "description": "Add your name and occupation",
            "completed": has_basic_profile,
            "required": True,
            "action_url": "/api/v1/users/me",
            "action_text": "Complete Profile",
        },
        {
            "step": OnboardingStep.PROFILE_PHOTO,
            "title": "Add Your Photo",
            "description": "Upload a profile picture to build trust",
            "completed": has_profile_photo,
            "required": True,
            "action_url": "/api/v1/users/me/photo/presign",
            "action_text": "Upload Photo",
        },
        {
            "step": OnboardingStep.PET_PROFILE,
            "title": "Create Pet Profile",
            "description": "Add details about your furry friend",
            "completed": has_pet,
            "required": True,
            "action_url": "/api/v1/pets",
            "action_text": "Add Pet",
        },
        {
            "step": OnboardingStep.PET_PHOTOS,
            "title": "Add Pet Photos",
            "description": "Upload at least one photo of your pet",
            "completed": has_active_pet,
            "required": True,
            "action_url": None,  # Depends on pet_id
            "action_text": "Upload Photos",
        },
        {
            "step": OnboardingStep.PREFERENCES,
            "title": "Set Your Preferences",
            "description": "Add bio and address for better matches",
            "completed": has_bio,
            "required": False,
            "action_url": "/api/v1/users/me",
            "action_text": "Set Preferences",
        },
    ]
    
    # Build step status list
    steps = [OnboardingStepStatus(**config) for config in steps_config]
    
    # Calculate progress
    completed_steps = sum(1 for s in steps if s.completed)
    total_steps = len(steps)
    completion_percentage = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
    
    # Determine current step (first incomplete step)
    current_step = OnboardingStep.COMPLETE
    for step_status in steps:
        if not step_status.completed:
            current_step = step_status.step
            break
    
    # Check if all required steps are done
    required_completed = all(s.completed for s in steps if s.required)
    is_complete = current_step == OnboardingStep.COMPLETE
    
    # Can start swiping if required steps done
    can_start_swiping = required_completed
    
    # Should show wizard if not all required steps done
    should_show_wizard = not required_completed
    
    return OnboardingStatus(
        current_step=current_step,
        total_steps=total_steps,
        completed_steps=completed_steps,
        completion_percentage=completion_percentage,
        is_complete=is_complete,
        steps=steps,
        can_start_swiping=can_start_swiping,
        should_show_wizard=should_show_wizard,
    )


@router.post("/skip-optional", status_code=200)
async def skip_optional_steps(
    user: User = Depends(get_current_user),
):
    """Mark optional steps as 'skipped' for the session
    
    This doesn't persist state but can be used by frontend to track user preference
    to skip optional onboarding steps like email verification.
    """
    return {
        "message": "Optional steps skipped. You can complete them later from your profile.",
        "skippable_steps": [
            OnboardingStep.EMAIL_VERIFICATION.value,
            OnboardingStep.PREFERENCES.value,
        ],
    }
