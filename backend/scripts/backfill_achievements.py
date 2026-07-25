"""Award the badges a user's existing data already qualifies them for.

Achievements are normally granted at the moment the triggering action happens —
you upload a photo, the route grants PROFILE_PHOTO. Anything written straight to
the database therefore earns nothing, which is why seeded accounts showed
"0 of 9 earned" while having a photo, a name, pets, matches and sent messages.

Criteria are derived from database state rather than from the seed script's data
structures, so this also repairs accounts whose badges were missed for any other
reason (a failed grant mid-request, rows edited by hand, an older seed).

    uv run python scripts/backfill_achievements.py          # report only
    uv run python scripts/backfill_achievements.py --apply  # insert the rows

seed_realistic_data.py calls sync_achievements() directly at the end of a run.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal  # noqa: E402

# User declares relationships to these by name, so they must be imported before
# SQLAlchemy configures its mappers — importing UserAchievement alone leaves
# those names unresolvable.
from app.models.match_preference import MatchPreference  # noqa: E402,F401
from app.models.pet_photo import PetPhoto  # noqa: E402,F401
from app.models.pet_profile import PetProfile  # noqa: E402,F401
from app.models.user import User  # noqa: E402,F401
from app.models.user_achievement import AchievementType, UserAchievement  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIVE_MATCHES_THRESHOLD = 5


async def _gather_state(session: AsyncSession) -> dict:
    """One row per user describing everything the badge rules care about."""
    result = await session.execute(
        text(
            """
            SELECT
                u.id,
                u.email,
                u.is_verified,
                u.profile_photo_url,
                u.full_name,
                u.occupation,
                u.bio,
                u.address,
                COALESCE(p.pet_count, 0)        AS pet_count,
                COALESCE(p.active_pet_count, 0) AS active_pet_count,
                COALESCE(p.photo_count, 0)      AS photo_count,
                COALESCE(m.match_count, 0)      AS match_count,
                COALESCE(s.message_count, 0)    AS message_count
            FROM users u
            LEFT JOIN (
                SELECT
                    pp.user_id,
                    COUNT(DISTINCT pp.id)                                       AS pet_count,
                    COUNT(DISTINCT pp.id) FILTER (WHERE pp.is_active)           AS active_pet_count,
                    COUNT(ph.id)                                                AS photo_count
                FROM pet_profiles pp
                LEFT JOIN pet_photos ph ON ph.pet_id = pp.id
                GROUP BY pp.user_id
            ) p ON p.user_id = u.id
            LEFT JOIN (
                SELECT pp.user_id, COUNT(DISTINCT mt.id) AS match_count
                FROM matches mt
                JOIN pet_profiles pp ON pp.id IN (mt.pet1_id, mt.pet2_id)
                WHERE mt.deleted_at IS NULL
                GROUP BY pp.user_id
            ) m ON m.user_id = u.id
            LEFT JOIN (
                SELECT pp.user_id, COUNT(msg.id) AS message_count
                FROM messages msg
                JOIN pet_profiles pp ON pp.id = msg.sender_pet_id
                WHERE msg.deleted_at IS NULL
                GROUP BY pp.user_id
            ) s ON s.user_id = u.id
            """
        )
    )
    return {row.id: row for row in result}


def _earned(row) -> set[AchievementType]:
    """Which badges this user's data qualifies them for."""
    filled = lambda v: bool(v and str(v).strip())  # noqa: E731

    earned: set[AchievementType] = set()

    if filled(row.profile_photo_url):
        earned.add(AchievementType.PROFILE_PHOTO)
    if filled(row.full_name):
        earned.add(AchievementType.FULL_NAME)
    if row.pet_count > 0:
        earned.add(AchievementType.PET_CREATED)
    if row.photo_count > 0:
        earned.add(AchievementType.PET_PHOTO)
    if row.match_count >= 1:
        earned.add(AchievementType.FIRST_MATCH)
    if row.match_count >= FIVE_MATCHES_THRESHOLD:
        earned.add(AchievementType.FIVE_MATCHES)
    if row.message_count >= 1:
        earned.add(AchievementType.FIRST_MESSAGE)
    if row.is_verified:
        earned.add(AchievementType.VERIFIED_EMAIL)

    # Mirrors GET /users/me/completion: 60% from five profile fields, 40% from
    # having at least one active pet. Both halves must be full for 100%.
    profile_fields = [
        row.profile_photo_url,
        row.full_name,
        row.occupation,
        row.bio,
        row.address,
    ]
    if all(filled(v) for v in profile_fields) and row.active_pet_count > 0:
        earned.add(AchievementType.PROFILE_COMPLETE)

    return earned


async def sync_achievements(session: AsyncSession, apply: bool = True) -> int:
    """Insert any missing achievement rows. Returns how many were added.

    Never removes an existing badge: losing one because a pet was deleted or a
    match was undone would be a worse experience than an occasional stale badge,
    and it matches how the app grants them (award-only, never revoked).
    """
    state = await _gather_state(session)

    existing_result = await session.execute(
        text("SELECT user_id, achievement_type FROM user_achievements")
    )
    existing: set[tuple] = {(r.user_id, r.achievement_type) for r in existing_result}

    to_add: list[UserAchievement] = []
    for user_id, row in state.items():
        for achievement in _earned(row):
            if (user_id, achievement.value) in existing:
                continue
            to_add.append(UserAchievement(user_id=user_id, achievement_type=achievement))

    if apply and to_add:
        session.add_all(to_add)
        await session.flush()

    return len(to_add)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the rows")
    args = parser.parse_args()

    logging.disable(logging.INFO)

    async with AsyncSessionLocal() as session:
        state = await _gather_state(session)
        print(f"\n{len(state)} users\n")
        for row in list(state.values())[:6]:
            names = sorted(a.value for a in _earned(row))
            print(f"  {row.email:34} {len(names)}/9  {', '.join(names)}")
        if len(state) > 6:
            print(f"  … and {len(state) - 6} more")

        added = await sync_achievements(session, apply=args.apply)
        if args.apply:
            await session.commit()
            print(f"\nGranted {added} achievements.\n")
        else:
            print(f"\nWould grant {added} achievements. Re-run with --apply.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
