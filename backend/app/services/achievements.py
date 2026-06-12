"""Achievement service for tracking and granting user badges"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_achievement import AchievementType, UserAchievement


ACHIEVEMENT_METADATA = {
    AchievementType.PROFILE_PHOTO: {
        "name": "Picture Perfect",
        "description": "Upload your profile photo",
        "icon": "📸",
    },
    AchievementType.FULL_NAME: {
        "name": "First Steps",
        "description": "Add your name to your profile",
        "icon": "👤",
    },
    AchievementType.PET_CREATED: {
        "name": "Pet Parent",
        "description": "Create your first pet profile",
        "icon": "🐕",
    },
    AchievementType.PET_PHOTO: {
        "name": "Show & Tell",
        "description": "Upload your pet's first photo",
        "icon": "📷",
    },
    AchievementType.FIRST_MATCH: {
        "name": "Match Maker",
        "description": "Get your first match",
        "icon": "💝",
    },
    AchievementType.FIVE_MATCHES: {
        "name": "Popular Paw",
        "description": "Achieve 5 matches",
        "icon": "⭐",
    },
    AchievementType.FIRST_MESSAGE: {
        "name": "Breaking the Ice",
        "description": "Send your first message",
        "icon": "💬",
    },
    AchievementType.PROFILE_COMPLETE: {
        "name": "All Set",
        "description": "Complete your profile 100%",
        "icon": "✨",
    },
    AchievementType.VERIFIED_EMAIL: {
        "name": "Verified",
        "description": "Verify your email address",
        "icon": "✅",
    },
}


async def grant_achievement(
    db: AsyncSession, user_id: uuid.UUID, achievement_type: AchievementType
) -> UserAchievement | None:
    """Grant an achievement to a user if they don't already have it"""
    # Check if already earned
    result = await db.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_type == achievement_type,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return None  # Already earned
    
    # Grant new achievement
    achievement = UserAchievement(
        user_id=user_id,
        achievement_type=achievement_type,
    )
    db.add(achievement)
    await db.commit()
    await db.refresh(achievement)
    
    return achievement


async def get_user_achievements(
    db: AsyncSession, user_id: uuid.UUID
) -> list[UserAchievement]:
    """Get all achievements earned by a user"""
    result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.earned_at.desc())
    )
    return list(result.scalars().all())


def get_achievement_metadata(achievement_type: AchievementType) -> dict:
    """Get display metadata for an achievement"""
    return ACHIEVEMENT_METADATA.get(
        achievement_type,
        {
            "name": achievement_type.value.replace("_", " ").title(),
            "description": "",
            "icon": "🏆",
        },
    )
