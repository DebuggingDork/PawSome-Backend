import time
import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import get_current_user
from fastapi import status
from redis.asyncio import Redis
from sqlalchemy import select
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
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

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
async def register( body: RegisterRequest , db:AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
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

    return TokenResponse(
        access_token = create_access_token(user.id),
        refresh_token = create_refresh_token(user.id),
        token_type = "Bearer"
    )

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginRequest , db :AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
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