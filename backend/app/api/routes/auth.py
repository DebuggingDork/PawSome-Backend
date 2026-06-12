from fastapi import APIRouter, HTTPException

from app.api.deps import get_current_user
from fastapi import status
from sqlalchemy import select
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
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
async def refresh(body: RefreshRequest , db:AsyncSession = Depends(get_db)):
    try:
        user_id = verify_token(body.refresh_token , TOKEN_TYPE_REFRESH)
    except ValueError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid or expired refresh token"
        )
    
    result  = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail = "User not found"
        )

    return TokenResponse(
        access_token = create_access_token(user.id),
        refresh_token = create_refresh_token(user.id),
        token_type = "Bearer"
    )

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user