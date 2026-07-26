from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.user_achievement import AchievementType
from app.schemas.achievement import AchievementBadge, AchievementResponse, AchievementSummary
from app.services import achievements

router = APIRouter(
    prefix="/achievements",
    tags=["achievements"],
)


@router.get("/me", response_model=AchievementSummary)
async def get_my_achievements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's badge progress, awarding anything newly qualified for.

    Badges are derived from account state on read rather than fired at each
    action point, so one added later is awarded retroactively and one missed
    because a request failed halfway is picked up next time.
    """
    fresh = await achievements.sync_user_achievements(db, user.id)
    newly_earned_types = {a.achievement_type for a in fresh}

    user_achievements = await achievements.get_user_achievements(db, user.id)
    earned_map = {a.achievement_type: a for a in user_achievements}

    def to_badge(achievement_type: AchievementType) -> AchievementBadge:
        meta = achievements.get_achievement_metadata(achievement_type)
        earned_achievement = earned_map.get(achievement_type)
        return AchievementBadge(
            type=achievement_type,
            name=meta["name"],
            description=meta["description"],
            icon=meta["icon"],
            earned=earned_achievement is not None,
            earned_at=earned_achievement.earned_at if earned_achievement else None,
        )

    badges = [to_badge(t) for t in AchievementType]

    total_available = len(AchievementType)
    total_earned = len(user_achievements)
    completion_percentage = int((total_earned / total_available) * 100) if total_available > 0 else 0
    
    # Recent achievements (last 5)
    recent = [
        AchievementResponse.model_validate(a)
        for a in user_achievements[:5]
    ]
    
    return AchievementSummary(
        total_earned=total_earned,
        total_available=total_available,
        completion_percentage=completion_percentage,
        badges=badges,
        recent_achievements=recent,
        newly_earned=[to_badge(t) for t in AchievementType if t in newly_earned_types],
    )
