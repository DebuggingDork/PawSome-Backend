"""Schemas for onboarding wizard flow"""
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class OnboardingStep(str, Enum):
    """Steps in the onboarding wizard"""
    EMAIL_VERIFICATION = "email_verification"
    PROFILE_BASICS = "profile_basics"
    PROFILE_PHOTO = "profile_photo"
    PET_PROFILE = "pet_profile"
    PET_PHOTOS = "pet_photos"
    PREFERENCES = "preferences"
    COMPLETE = "complete"


class OnboardingStepStatus(BaseModel):
    """Status of a single onboarding step"""
    step: OnboardingStep
    title: str = Field(description="Display title for this step")
    description: str = Field(description="What to do in this step")
    completed: bool = Field(description="Whether this step is done")
    required: bool = Field(description="Whether this step is required")
    action_url: str | None = Field(description="API endpoint to complete this step")
    action_text: str | None = Field(description="CTA button text")


class OnboardingStatus(BaseModel):
    """Complete onboarding wizard status"""
    current_step: OnboardingStep = Field(description="Next step to complete")
    total_steps: int = Field(description="Total number of steps")
    completed_steps: int = Field(description="Number of completed steps")
    completion_percentage: int = Field(ge=0, le=100, description="Overall completion (0-100)")
    is_complete: bool = Field(description="True if onboarding is fully complete")
    steps: list[OnboardingStepStatus] = Field(description="All onboarding steps with status")
    
    # Quick flags
    can_start_swiping: bool = Field(description="Whether user can start browsing pets")
    should_show_wizard: bool = Field(description="Whether to show onboarding UI")
