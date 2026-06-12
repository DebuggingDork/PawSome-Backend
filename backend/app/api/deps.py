from app.models.pet_profile import PetProfile
from app.models.user import User
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_token, TOKEN_TYPE_ACCESS
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from sqlalchemy import select

# Request
#   ↓
# Authorization: Bearer <token>
#   ↓
# verify_token() extracts and validates token
#   ↓
# user_id obtained from token payload
#   ↓
# SELECT user FROM database
#   ↓
# Return User object to route

bearer_scheme = HTTPBearer()
bearer_scheme_optional = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:

    try:
        user_id = verify_token(
            credentials.credentials,
            TOKEN_TYPE_ACCESS
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """For public endpoints that behave differently when logged in
    (e.g. a pet owner viewing their own pet sees full data)."""
    if credentials is None:
        return None

    try:
        user_id = verify_token(credentials.credentials, TOKEN_TYPE_ACCESS)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def require_active_pet(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PetProfile:
    """Gate for actions that require a registered pet (swipe, chat, etc.).

    Users without a pet can still browse, but routes using this dependency
    return 403 PET_PROFILE_REQUIRED so the frontend can prompt them to
    register a pet first.
    """
    result = await db.execute(
        select(PetProfile)
        .where(
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
        .order_by(PetProfile.created_at)
        .limit(1)
    )
    pet = result.scalar_one_or_none()

    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PET_PROFILE_REQUIRED",
        )

    return pet