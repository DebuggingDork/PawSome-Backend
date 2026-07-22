from typing import Literal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Password must be at least 8 characters long")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str 

class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="Refresh token")

class TokenResponse(BaseModel):
    access_token: str = Field(description="Access token")
    refresh_token: str = Field(description="Refresh token")
    token_type: str = Field(description="Token type")

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    is_verified: bool

    model_config = {
        "from_attributes": True,
    }


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    full_name: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=500)
    profile_photo_url: str | None = Field(default=None, max_length=512)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class UserPublicProfile(BaseModel):
    """Public profile - visible to anyone who can see their pets"""
    id: UUID
    full_name: str | None
    occupation: str | None
    bio: str | None
    profile_photo_url: str | None

    model_config = {
        "from_attributes": True,
    }


class UserPrivateProfile(UserPublicProfile):
    """Private profile - includes address, only visible to matched connections"""
    address: str | None

    model_config = {
        "from_attributes": True,
    }


class UserFullProfile(UserPrivateProfile):
    """Full profile - includes email, only for the owner"""
    email: EmailStr
    is_verified: bool
    # Exact coordinates are owner-only (never surfaced on UserPublicProfile/UserPrivateProfile).
    latitude: float | None
    longitude: float | None

    model_config = {
        "from_attributes": True,
    }


class UserPhotoPresignRequest(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class UserPhotoPresignResponse(BaseModel):
    upload_url: str = Field(description="PUT the file here with the same Content-Type")
    object_key: str = Field(description="Pass back to the confirm endpoint after upload")
    expires_in: int = Field(description="Seconds until the upload URL expires")


class UserPhotoConfirmRequest(BaseModel):
    object_key: str = Field(min_length=1, max_length=512)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, description="Verification token from email")


class ResendVerificationRequest(BaseModel):
    email: EmailStr = Field(description="Email address to resend verification to")


class ProfileCompletionStatus(BaseModel):
    """Profile completion tracking for gamified onboarding"""
    completion_percentage: int = Field(ge=0, le=100, description="Overall profile completion (0-100)")
    is_complete: bool = Field(description="True if all required fields are filled")
    completed_fields: list[str] = Field(description="List of completed field names")
    missing_fields: list[str] = Field(description="List of missing field names")
    suggestions: list[str] = Field(description="Friendly suggestions for next steps")
    
    # Breakdown by category
    profile_fields_complete: int = Field(ge=0, le=100, description="Profile fields completion (0-100)")
    pet_profile_complete: int = Field(ge=0, le=100, description="Pet profile completion (0-100)")
    
    # Counts
    total_pets: int = Field(description="Number of pets created")
    active_pets: int = Field(description="Number of active pets (with photos)")
    
    # Milestones
    has_profile_photo: bool
    has_basic_info: bool
    has_bio: bool
    has_address: bool
    has_at_least_one_pet: bool
    has_active_pet: bool