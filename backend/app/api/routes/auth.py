import time
import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import get_current_user
from fastapi import status
from redis.asyncio import Redis
from sqlalchemy import func, select
from app.core.redis import get_redis
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token_payload,
)

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from fastapi import Depends
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services import email as email_service

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

REVOKED_TOKEN_PREFIX = "revoked_token:"


async def _revoke_token(redis: Redis, payload: dict) -> None:
    """Denylist a token's jti in Redis until the token would expire anyway."""
    jti = payload.get("jti")
    if not jti:
        return
    ttl = int(payload["exp"] - time.time())
    if ttl > 0:
        await redis.set(f"{REVOKED_TOKEN_PREFIX}{jti}", "1", ex=ttl)


async def _is_token_revoked(redis: Redis, payload: dict) -> bool:
    jti = payload.get("jti")
    if not jti:
        # Tokens issued before jti existed can't be revoked — reject them.
        return True
    return await redis.exists(f"{REVOKED_TOKEN_PREFIX}{jti}") == 1

@router.post("/register",response_model=TokenResponse,status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    existing = await db.execute(select(User).where(func.lower(User.email) == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user = User(
        email = body.email,
        password_hash = hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email
    token = await email_service.generate_verification_token(redis, str(user.id))
    email_service.send_verification_email(user.email, token)

    return TokenResponse(
        access_token = create_access_token(user.id),
        refresh_token = create_refresh_token(user.id),
        token_type = "Bearer"
    )

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginRequest , db :AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(func.lower(User.email) == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return TokenResponse(
        access_token = create_access_token(user.id),
        refresh_token = create_refresh_token(user.id),
        token_type = "Bearer"
    )

@router.post("/refresh",response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    try:
        payload = verify_token_payload(body.refresh_token , TOKEN_TYPE_REFRESH)
    except ValueError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid or expired refresh token"
        )

    if await _is_token_revoked(redis, payload):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Refresh token has been revoked"
        )

    result  = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail = "User not found"
        )

    # Rotation: the old refresh token is single-use. If it leaks and someone
    # replays it later, it's already dead.
    await _revoke_token(redis, payload)

    return TokenResponse(
        access_token = create_access_token(user.id),
        refresh_token = create_refresh_token(user.id),
        token_type = "Bearer"
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, redis: Redis = Depends(get_redis)):
    """Revoke the refresh token so it can't mint new access tokens.
    The client should also discard both tokens locally; the short-lived
    access token simply expires on its own."""
    try:
        payload = verify_token_payload(body.refresh_token, TOKEN_TYPE_REFRESH)
    except ValueError:
        # Already expired/invalid — logout is idempotent, nothing to revoke.
        return

    await _revoke_token(redis, payload)

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Verify user email address using token from email"""
    user_id = await email_service.verify_token(redis, body.token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    # Get user and mark as verified
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.is_verified:
        # Already verified, that's okay
        return user
    
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    
    # Send welcome email
    email_service.send_welcome_email(user.email, user.full_name)
    
    # Grant achievement
    from app.models.user_achievement import AchievementType
    from app.services import achievements
    
    await achievements.grant_achievement(db, user.id, AchievementType.VERIFIED_EMAIL)
    
    return user


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Send a password reset link if the email is registered.

    Always returns the same generic message so the endpoint can't be used
    to enumerate which emails have accounts.
    """
    result = await db.execute(select(User).where(func.lower(User.email) == body.email))
    user = result.scalar_one_or_none()

    if user:
        token = await email_service.generate_password_reset_token(redis, str(user.id))
        email_service.send_password_reset_email(user.email, token)

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Set a new password using a token from the forgot-password email"""
    user_id = await email_service.verify_password_reset_token(redis, body.token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.password_hash = hash_password(body.new_password)
    await db.commit()

    return {"message": "Password has been reset successfully"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Resend verification email"""
    result = await db.execute(
        select(User).where(func.lower(User.email) == body.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal if email exists for security
        return {"message": "If the email exists, a verification link has been sent"}
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )
    
    # Generate new token and send email
    token = await email_service.generate_verification_token(redis, str(user.id))
    email_service.send_verification_email(user.email, token)
    
    return {"message": "Verification email sent"}
