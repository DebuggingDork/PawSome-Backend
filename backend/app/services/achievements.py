"""Achievement service for tracking and granting user badges"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_achievement import AchievementType, UserAchievement


FIVE_MATCHES_THRESHOLD = 5
TEN_MATCHES_THRESHOLD = 10
FIFTY_SWIPES_THRESHOLD = 50
HUNDRED_MESSAGES_THRESHOLD = 100
FULL_GALLERY_PHOTOS = 5
WEEK_ONE_DAYS = 7


ACHIEVEMENT_METADATA = {
    AchievementType.FULL_NAME: {
        "name": "First Steps",
        "description": "Add your name to your profile",
        "icon": "👤",
    },
    AchievementType.VERIFIED_EMAIL: {
        "name": "Verified",
        "description": "Verify your email address",
        "icon": "✅",
    },
    AchievementType.PROFILE_PHOTO: {
        "name": "Picture Perfect",
        "description": "Upload your profile photo",
        "icon": "📸",
    },
    AchievementType.ON_THE_MAP: {
        "name": "On the Map",
        "description": "Add your location so nearby owners can find you",
        "icon": "📍",
    },
    AchievementType.STORYTELLER: {
        "name": "Storyteller",
        "description": "Write a bio worth reading",
        "icon": "✍️",
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
    AchievementType.PROFILE_COMPLETE: {
        "name": "All Set",
        "description": "Complete your profile 100%",
        "icon": "✨",
    },
    AchievementType.FIRST_SWIPE: {
        "name": "Nice to Meet You",
        "description": "Swipe on your first pet",
        "icon": "👋",
    },
    AchievementType.FIFTY_SWIPES: {
        "name": "Serial Swiper",
        "description": f"Swipe on {FIFTY_SWIPES_THRESHOLD} pets",
        "icon": "🔥",
    },
    AchievementType.SUPER_WOOF: {
        "name": "Super Woof",
        "description": "Send your first Super Woof",
        "icon": "🌟",
    },
    AchievementType.FIRST_MATCH: {
        "name": "Match Maker",
        "description": "Get your first match",
        "icon": "💝",
    },
    AchievementType.FIVE_MATCHES: {
        "name": "Popular Paw",
        "description": f"Reach {FIVE_MATCHES_THRESHOLD} matches",
        "icon": "⭐",
    },
    AchievementType.TEN_MATCHES: {
        "name": "Social Butterfly",
        "description": f"Reach {TEN_MATCHES_THRESHOLD} matches",
        "icon": "🦋",
    },
    AchievementType.FIRST_MESSAGE: {
        "name": "Breaking the Ice",
        "description": "Send your first message",
        "icon": "💬",
    },
    AchievementType.HUNDRED_MESSAGES: {
        "name": "Chatterbox",
        "description": f"Send {HUNDRED_MESSAGES_THRESHOLD} messages",
        "icon": "💌",
    },
    AchievementType.FIRST_PLAYDATE: {
        "name": "Park Life",
        "description": "Propose a real-world playdate",
        "icon": "🌳",
    },
    AchievementType.PLAYDATE_CONFIRMED: {
        "name": "It's a Date",
        "description": "Have a playdate accepted",
        "icon": "📅",
    },
    AchievementType.FULL_GALLERY: {
        "name": "Photogenic",
        "description": f"Fill all {FULL_GALLERY_PHOTOS} photo slots for one pet",
        "icon": "🖼️",
    },
    AchievementType.MULTI_PET: {
        "name": "Full House",
        "description": "Look after more than one pet",
        "icon": "🏠",
    },
    AchievementType.WEEK_ONE: {
        "name": "Week One",
        "description": f"Spend {WEEK_ONE_DAYS} days on PawSome",
        "icon": "🗓️",
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


_STATE_SQL = text(
    """
    SELECT
        u.is_verified,
        u.profile_photo_url,
        u.full_name,
        u.occupation,
        u.bio,
        u.address,
        u.latitude,
        u.created_at,
        COALESCE(p.pet_count, 0)        AS pet_count,
        COALESCE(p.active_pet_count, 0) AS active_pet_count,
        COALESCE(p.photo_count, 0)      AS photo_count,
        COALESCE(p.max_pet_photos, 0)   AS max_pet_photos,
        COALESCE(m.match_count, 0)      AS match_count,
        COALESCE(s.message_count, 0)    AS message_count,
        COALESCE(w.swipe_count, 0)      AS swipe_count,
        COALESCE(w.super_count, 0)      AS super_count,
        COALESCE(d.proposed_count, 0)   AS proposed_count,
        COALESCE(d.accepted_count, 0)   AS accepted_count
    FROM users u
    LEFT JOIN (
        SELECT
            pp.user_id,
            COUNT(DISTINCT pp.id)                             AS pet_count,
            COUNT(DISTINCT pp.id) FILTER (WHERE pp.is_active) AS active_pet_count,
            COUNT(ph.id)                                      AS photo_count,
            COALESCE(MAX(per_pet.n), 0)                       AS max_pet_photos
        FROM pet_profiles pp
        LEFT JOIN pet_photos ph ON ph.pet_id = pp.id
        LEFT JOIN (
            SELECT pet_id, COUNT(*) AS n FROM pet_photos GROUP BY pet_id
        ) per_pet ON per_pet.pet_id = pp.id
        WHERE pp.user_id = :uid
        GROUP BY pp.user_id
    ) p ON TRUE
    LEFT JOIN (
        SELECT COUNT(DISTINCT mt.id) AS match_count
        FROM matches mt
        JOIN pet_profiles pp ON pp.id IN (mt.pet1_id, mt.pet2_id)
        WHERE mt.deleted_at IS NULL AND pp.user_id = :uid
    ) m ON TRUE
    LEFT JOIN (
        SELECT COUNT(msg.id) AS message_count
        FROM messages msg
        JOIN pet_profiles pp ON pp.id = msg.sender_pet_id
        WHERE msg.deleted_at IS NULL AND pp.user_id = :uid
    ) s ON TRUE
    LEFT JOIN (
        SELECT
            COUNT(*)                                            AS swipe_count,
            COUNT(*) FILTER (WHERE sw.action = 'SUPER_LIKE')    AS super_count
        FROM swipes sw
        JOIN pet_profiles pp ON pp.id = sw.swiper_pet_id
        WHERE pp.user_id = :uid
    ) w ON TRUE
    LEFT JOIN (
        SELECT
            COUNT(*) FILTER (WHERE pd.proposed_by_pet_id = pp.id)   AS proposed_count,
            COUNT(*) FILTER (WHERE pd.status = 'ACCEPTED')          AS accepted_count
        FROM playdates pd
        JOIN pet_profiles pp ON pp.id IN (pd.proposed_by_pet_id, pd.proposed_to_pet_id)
        WHERE pp.user_id = :uid
    ) d ON TRUE
    WHERE u.id = :uid
    """
)


def _qualifies(row) -> set[AchievementType]:
    """Every badge this user's data currently entitles them to.

    Deriving from state rather than firing at each action point means a badge
    added later is awarded retroactively, and one missed because a request failed
    halfway is picked up on the next read. It also keeps the rules in one place
    instead of scattered across eight routes.
    """
    filled = lambda v: bool(v and str(v).strip())  # noqa: E731
    earned: set[AchievementType] = set()

    if filled(row.full_name):
        earned.add(AchievementType.FULL_NAME)
    if row.is_verified:
        earned.add(AchievementType.VERIFIED_EMAIL)
    if filled(row.profile_photo_url):
        earned.add(AchievementType.PROFILE_PHOTO)
    if row.latitude is not None or filled(row.address):
        earned.add(AchievementType.ON_THE_MAP)
    if filled(row.bio):
        earned.add(AchievementType.STORYTELLER)
    if row.pet_count > 0:
        earned.add(AchievementType.PET_CREATED)
    if row.photo_count > 0:
        earned.add(AchievementType.PET_PHOTO)

    # Mirrors GET /users/me/completion: 60% from five profile fields, 40% from
    # having at least one active pet. Both halves must be full for 100%.
    if (
        all(filled(v) for v in (row.profile_photo_url, row.full_name, row.occupation, row.bio, row.address))
        and row.active_pet_count > 0
    ):
        earned.add(AchievementType.PROFILE_COMPLETE)

    if row.swipe_count >= 1:
        earned.add(AchievementType.FIRST_SWIPE)
    if row.swipe_count >= FIFTY_SWIPES_THRESHOLD:
        earned.add(AchievementType.FIFTY_SWIPES)
    if row.super_count >= 1:
        earned.add(AchievementType.SUPER_WOOF)
    if row.match_count >= 1:
        earned.add(AchievementType.FIRST_MATCH)
    if row.match_count >= FIVE_MATCHES_THRESHOLD:
        earned.add(AchievementType.FIVE_MATCHES)
    if row.match_count >= TEN_MATCHES_THRESHOLD:
        earned.add(AchievementType.TEN_MATCHES)

    if row.message_count >= 1:
        earned.add(AchievementType.FIRST_MESSAGE)
    if row.message_count >= HUNDRED_MESSAGES_THRESHOLD:
        earned.add(AchievementType.HUNDRED_MESSAGES)
    if row.proposed_count >= 1:
        earned.add(AchievementType.FIRST_PLAYDATE)
    if row.accepted_count >= 1:
        earned.add(AchievementType.PLAYDATE_CONFIRMED)

    if row.max_pet_photos >= FULL_GALLERY_PHOTOS:
        earned.add(AchievementType.FULL_GALLERY)
    if row.pet_count > 1:
        earned.add(AchievementType.MULTI_PET)
    if row.created_at is not None:
        now = datetime.now(row.created_at.tzinfo) if row.created_at.tzinfo else datetime.utcnow()
        if (now - row.created_at) >= timedelta(days=WEEK_ONE_DAYS):
            earned.add(AchievementType.WEEK_ONE)

    return earned


async def sync_user_achievements(db: AsyncSession, user_id: uuid.UUID) -> list[UserAchievement]:
    """Award anything this user now qualifies for. Returns only what was new.

    Called when the badges page is read, so the list is always truthful without
    every route having to remember which badges its action might unlock. Only
    ever adds: a badge, once earned, is never taken away.
    """
    result = await db.execute(_STATE_SQL, {"uid": user_id})
    row = result.first()
    if row is None:
        return []

    already = {a.achievement_type for a in await get_user_achievements(db, user_id)}
    missing = _qualifies(row) - already
    if not missing:
        return []

    granted = [UserAchievement(user_id=user_id, achievement_type=t) for t in missing]
    db.add_all(granted)
    await db.commit()
    for a in granted:
        await db.refresh(a)
    return granted


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
