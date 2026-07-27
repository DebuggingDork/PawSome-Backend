import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from redis.asyncio import Redis
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_verified_email
from app.core.database import get_db
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis
from app.models.favorite import Favorite
from app.models.block import Block
from app.models.match import Match
from app.models.match_preference import MatchPreference
from app.models.notification import Notification, NotificationType
from app.models.pet_profile import PetProfile
from app.models.swipe import Swipe, SwipeAction
from app.models.user import User
from app.services.block_cache import cache_block
from app.services.match_scoring import calculate_match_score
from app.services.notification_manager import manager as notification_manager
from app.schemas.match import (
    MarkNotificationReadRequest,
    MatchResponse,
    MatchSummaryResponse,
    NotificationResponse,
    NotificationWithDetails,
    PetRelationshipEntry,
    PetRelationshipResponse,
    SuperWoofStatus,
    SwipeRequest,
    SwipeResponse,
)
from app.schemas.pet import PetPublicResponse, PetResponse
from app.schemas.statistics import (
    DailySwipeStats,
    SwipeHistoryItem,
    SwipeHistoryResponse,
    SwipeStatisticsResponse,
    TopBreed,
)
from app.schemas.browse import BrowsePetsResponse, MatchCandidateResponse
from app.schemas.undo import UndoSwipeRequest, UndoSwipeResponse
from app.schemas.unmatch import UnmatchRequest, UnmatchResponse
from app.utils.distance import haversine_distance

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/matches",
    tags=["matches"],
)

# Super Woof — one free priority like per user per rolling 24h window.
SUPER_WOOF_LIMIT = 1
SUPER_WOOF_WINDOW_SECONDS = 86400

# How many rows the Discover deck pulls before ranking. Ranking has to see the
# whole eligible pool or it just ranks an arbitrary prefix of it; the page size
# is applied afterwards.
CANDIDATE_POOL_SIZE = 500

# Stand-in used for sorting and scoring when a real distance can't be computed,
# large enough to sort after every genuine distance (the radius caps at 5000km).
UNKNOWN_DISTANCE_KM = 1e9


async def _open_match(db: AsyncSession, pet_a_id: uuid.UUID, pet_b_id: uuid.UUID) -> tuple[Match, bool]:
    """Return the live match for a pair, creating or reviving one as needed.

    `uq_match_pair` is unique on (pet1_id, pet2_id) with no regard for
    deleted_at, so a pair that has ever matched already owns its row forever.
    Inserting a second one raises IntegrityError — which is what every path
    that only looked for a *live* match did, turning any rematch after an
    unmatch into a 500.

    Returns (match, is_new) where is_new is False when an existing live match
    was found, so callers don't announce a match that was already there.
    """
    pet1_id, pet2_id = sorted([pet_a_id, pet_b_id])

    existing_result = await db.execute(
        select(Match).where(Match.pet1_id == pet1_id, Match.pet2_id == pet2_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        if existing.deleted_at is None:
            return existing, False
        # Reviving rather than inserting. The old messages come back with it —
        # the row is the conversation — which is the right trade against
        # destroying message history on an unmatch that might be reversed.
        existing.deleted_at = None
        existing.created_at = datetime.now(timezone.utc)
        return existing, True

    match = Match(pet1_id=pet1_id, pet2_id=pet2_id)
    db.add(match)
    await db.flush()
    return match, True


async def _push_notification(notification: Notification, other_pet: PetProfile) -> None:
    """Push a just-created Notification to its recipient over the live WS, if
    they're connected. The row is already saved either way — this only
    affects how fast they find out.

    Best-effort by design: the delivery path goes through Redis, and a Redis
    outage must not turn an otherwise-successful swipe or accept into a 500
    *after* the database has already been committed. The failure is logged
    loudly instead, because the visible symptom (no toast, no live badge) is
    otherwise indistinguishable from the feature simply not working.
    """
    try:
        await _broadcast_notification(notification, other_pet)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "live notification push FAILED (row %s is saved; recipient %s will "
            "see it on next fetch): %s: %s",
            notification.id, notification.user_id, type(exc).__name__, exc,
        )


async def _broadcast_notification(notification: Notification, other_pet: PetProfile) -> None:
    await notification_manager.broadcast_to_user(
        str(notification.user_id),
        {
            "type": "notification",
            "data": {
                "id": str(notification.id),
                "notification_type": notification.notification_type.value,
                "message": notification.message,
                "is_read": notification.is_read,
                "is_super": notification.is_super,
                "created_at": notification.created_at.isoformat(),
                "match_id": str(notification.match_id) if notification.match_id else None,
                "other_pet": {
                    "id": str(other_pet.id),
                    "name": other_pet.name,
                    "primary_photo_url": other_pet.primary_photo_url,
                },
            },
        },
    )


@router.websocket("/notifications/ws")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """Real-time push for new_like/new_match/new_message notifications.
    Connect: ws://localhost:8000/matches/notifications/ws?token=your-jwt-token
    The row is always saved via the REST endpoints regardless of whether this
    socket is connected — this is purely a "find out faster" channel."""
    from app.core.security import verify_token

    try:
        user_id = verify_token(token, "access")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Same reasoning as the chat socket: accept before the user lookup and the
    # Redis handshake, so the client isn't held in CONNECTING for the length of
    # two remote round trips on every page load.
    await websocket.accept()

    async for db in get_db():
        try:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            redis = await get_redis()
            if not notification_manager.redis_client:
                await notification_manager.initialize(redis)

            await notification_manager.connect(websocket, str(user.id))
            try:
                while True:
                    # No client->server messages expected; just keep the
                    # connection open and detect disconnects.
                    await websocket.receive_text()
            except WebSocketDisconnect:
                notification_manager.disconnect(str(user.id), websocket)
        finally:
            await db.close()


@router.post("/swipe", response_model=SwipeResponse)
async def swipe_on_pet(
    body: SwipeRequest,
    # Swiping is the point at which a user starts appearing to strangers and can
    # trigger notifications on someone else's account, so it's the natural place to
    # require a proven address rather than blocking signup on mail delivery.
    user: User = Depends(require_verified_email),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """
    Swipe on a pet (like, skip, or super_like).
    - Right swipe (like): Sends notification to target pet owner, they must accept/reject
    - Super Woof (super_like): Same as like, but limited to 1/day and surfaces at
      the top of the target's "likes you" list with a star badge
    - Left swipe (skip): No notification sent

    Validates:
    - Both pets exist and are active
    - Swiper pet belongs to current user
    - Same species (dogs can only match with dogs, etc.)
    - Not swiping on your own pet
    - Haven't already swiped on this pet
    - Super Woof: caller hasn't used today's allowance
    """
    # Verify the swiper pet belongs to the user
    swiper_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == body.pet_id,
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
    )
    swiper_pet = swiper_result.scalar_one_or_none()

    # Every rejection below is logged with the reason and the ids involved.
    # These all surface to the client as a bare 400/404, and a log full of
    # "POST /matches/swipe 400" said nothing about which of the five distinct
    # causes had fired — the species check in particular was rejecting an entire
    # deck at a time with no trace of why.
    def _reject(status_code: int, detail: str) -> HTTPException:
        logger.warning(
            "swipe rejected (%s): %s | user=%s swiper_pet=%s target_pet=%s action=%s",
            status_code, detail, user.id, body.pet_id, body.target_pet_id, body.action,
        )
        return HTTPException(status_code=status_code, detail=detail)

    if not swiper_pet:
        raise _reject(
            status.HTTP_404_NOT_FOUND,
            "Your pet not found or inactive",
        )

    # Verify target pet exists and is active
    target_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == body.target_pet_id,
            PetProfile.is_active.is_(True),
        )
    )
    target_pet = target_result.scalar_one_or_none()

    if not target_pet:
        raise _reject(
            status.HTTP_404_NOT_FOUND,
            "Target pet not found or inactive",
        )

    # Can't swipe on your own pet
    if target_pet.user_id == user.id:
        raise _reject(
            status.HTTP_400_BAD_REQUEST,
            "Cannot swipe on your own pet",
        )

    # Must be same species - inter-species matching not allowed
    if swiper_pet.species != target_pet.species:
        raise _reject(
            status.HTTP_400_BAD_REQUEST,
            f"{swiper_pet.name} is a {swiper_pet.species.value} and {target_pet.name} "
            f"is a {target_pet.species.value} — pets can only match within their own species.",
        )

    # Check if already swiped on this pet
    existing_swipe = await db.execute(
        select(Swipe).where(
            Swipe.swiper_pet_id == body.pet_id,
            Swipe.target_pet_id == body.target_pet_id,
        )
    )
    if existing_swipe.scalar_one_or_none():
        raise _reject(
            status.HTTP_400_BAD_REQUEST,
            f"You have already swiped on {target_pet.name}.",
        )

    # Charge today's Super Woof allowance only once the swipe is actually
    # going to happen — this used to run before the checks above, so a
    # super_like that failed validation (already swiped, own pet, species
    # mismatch, ...) still burned the caller's one-per-day allowance for
    # nothing.
    if body.action == "super_like":
        await check_rate_limit(
            redis=redis,
            user_id=str(user.id),
            key_prefix="super_woof",
            limit=SUPER_WOOF_LIMIT,
            window=SUPER_WOOF_WINDOW_SECONDS,
        )

    # Create the swipe
    action_map = {
        "like": SwipeAction.LIKE,
        "skip": SwipeAction.SKIP,
        "super_like": SwipeAction.SUPER_LIKE,
    }
    is_super = body.action == "super_like"
    swipe = Swipe(
        swiper_pet_id=body.pet_id,
        target_pet_id=body.target_pet_id,
        action=action_map[body.action],
    )
    db.add(swipe)

    # A like either completes a mutual pair (instant match) or waits for the
    # other owner to accept it from "Likes you".
    #
    # Nothing used to close the mutual case, and /likes-received hides anyone
    # you have already swiped on — so if A liked B and B then liked A from
    # Discover, A vanished from B's "Likes you" list before B could ever accept,
    # and no match could be created by either side again. Two people who both
    # said yes were left with two notifications and no conversation.
    reciprocal_like = None
    if body.action in ("like", "super_like"):
        reciprocal_result = await db.execute(
            select(Swipe).where(
                Swipe.swiper_pet_id == body.target_pet_id,
                Swipe.target_pet_id == body.pet_id,
                Swipe.action.in_([SwipeAction.LIKE, SwipeAction.SUPER_LIKE]),
                Swipe.is_undone.is_(False),
            )
        )
        reciprocal_like = reciprocal_result.scalar_one_or_none()

    notification_target: Notification | None = None
    match: Match | None = None
    match_notifications: list[tuple[Notification, PetProfile]] = []

    if reciprocal_like is not None:
        match, is_new_match = await _open_match(db, body.pet_id, body.target_pet_id)
        if is_new_match:
            your_match_notif = Notification(
                user_id=user.id,
                notification_type=NotificationType.NEW_MATCH,
                pet_id=body.pet_id,
                related_pet_id=body.target_pet_id,
                match_id=match.id,
                message=f"It's a match! {swiper_pet.name} and {target_pet.name} both said yes!",
            )
            other_match_notif = Notification(
                user_id=target_pet.user_id,
                notification_type=NotificationType.NEW_MATCH,
                pet_id=body.target_pet_id,
                related_pet_id=body.pet_id,
                match_id=match.id,
                message=f"It's a match! {target_pet.name} and {swiper_pet.name} both said yes!",
            )
            db.add(your_match_notif)
            db.add(other_match_notif)
            match_notifications = [
                (your_match_notif, target_pet),
                (other_match_notif, swiper_pet),
            ]
    elif body.action in ("like", "super_like"):
        # Send "NEW_LIKE" notification to target pet owner
        notification_target = Notification(
            user_id=target_pet.user_id,
            notification_type=NotificationType.NEW_LIKE,
            pet_id=body.target_pet_id,
            related_pet_id=body.pet_id,
            match_id=None,  # No match yet — they accept or reject from "Likes you"
            message=(
                f"🌟 {swiper_pet.name} Super Woofed {target_pet.name}!"
                if is_super
                else f"{swiper_pet.name} is interested in {target_pet.name}!"
            ),
            is_super=is_super,
        )
        db.add(notification_target)

    # Auto-remove favorite: if pet had favorited the target, soft-delete it on swipe
    existing_favorite_result = await db.execute(
        select(Favorite).where(
            Favorite.pet_id == body.pet_id,
            Favorite.target_pet_id == body.target_pet_id,
            Favorite.deleted_at.is_(None),
        )
    )
    existing_favorite = existing_favorite_result.scalar_one_or_none()
    if existing_favorite is not None:
        existing_favorite.deleted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(swipe)

    if notification_target is not None:
        await db.refresh(notification_target)
        await _push_notification(notification_target, swiper_pet)

    for notification, other_pet in match_notifications:
        await db.refresh(notification)
        await _push_notification(notification, other_pet)

    if match is not None:
        logger.info(
            "match created from mutual like: match=%s %s(%s) <-> %s(%s)",
            match.id, swiper_pet.name, body.pet_id, target_pet.name, body.target_pet_id,
        )
    elif notification_target is not None:
        logger.info(
            "%s sent: %s(%s) -> %s(%s), notified user=%s",
            "super woof" if is_super else "like",
            swiper_pet.name, body.pet_id, target_pet.name, body.target_pet_id,
            target_pet.user_id,
        )

    return SwipeResponse(
        id=swipe.id,
        swiper_pet_id=swipe.swiper_pet_id,
        target_pet_id=swipe.target_pet_id,
        action=swipe.action.value,
        is_match=match is not None,
        match_id=match.id if match is not None else None,
        created_at=swipe.created_at,
    )


@router.get("/super-woof/remaining", response_model=SuperWoofStatus)
async def get_super_woof_remaining(
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """How many Super Woofs the caller has left today, for the Discover button state."""
    key = f"rate_limit:super_woof:{user.id}"
    used_raw = await redis.get(key)
    used = int(used_raw) if used_raw else 0
    return SuperWoofStatus(
        remaining=max(0, SUPER_WOOF_LIMIT - used),
        limit=SUPER_WOOF_LIMIT,
        window_seconds=SUPER_WOOF_WINDOW_SECONDS,
    )


@router.get("/my-matches", response_model=list[MatchSummaryResponse])
async def get_my_matches(
    pet_id: uuid.UUID | None = Query(default=None, description="Filter by specific pet"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all matches for the current user's pets, each with the other pet resolved.
    Optionally filter by a specific pet ID.
    """

    # Every pet the caller owns, active or not. Filtering on is_active here hid
    # a user's own conversations the moment they deactivated the pet that made
    # the match, while the other side kept seeing the chat and could still send
    # into it. Ownership is what decides access; activeness only decides whether
    # a pet is discoverable.
    user_pets_result = await db.execute(
        select(PetProfile.id).where(PetProfile.user_id == user.id)
    )
    user_pet_ids = [row[0] for row in user_pets_result.all()]

    if not user_pet_ids:
        return []

    # Filter by specific pet if provided
    if pet_id:
        if pet_id not in user_pet_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pet does not belong to you",
            )
        user_pet_ids = [pet_id]

    # Find matches where any of user's pets are involved
    matches_result = await db.execute(
        select(Match)
        .where(
            or_(
                Match.pet1_id.in_(user_pet_ids),
                Match.pet2_id.in_(user_pet_ids),
            ),
            Match.deleted_at.is_(None),
        )
        .order_by(Match.created_at.desc())
    )

    matches = matches_result.scalars().all()
    if not matches:
        return []

    own_ids = set(user_pet_ids)
    other_ids = {
        (m.pet2_id if m.pet1_id in own_ids else m.pet1_id) for m in matches
    }

    # No is_active filter: a match with a since-deactivated pet is still a real
    # conversation with real history, and dropping it here is what emptied the
    # caller's entire Matches/Chat list before.
    other_pets_result = await db.execute(
        select(PetProfile)
        .options(selectinload(PetProfile.user))
        .where(PetProfile.id.in_(other_ids))
    )
    other_pets = {p.id: p for p in other_pets_result.scalars().all()}

    summaries: list[MatchSummaryResponse] = []
    for match in matches:
        your_pet_id = match.pet1_id if match.pet1_id in own_ids else match.pet2_id
        other_pet = other_pets.get(
            match.pet2_id if match.pet1_id in own_ids else match.pet1_id
        )
        if other_pet is None:
            # The pet row is gone entirely (hard delete) — nothing to show.
            continue
        summaries.append(
            MatchSummaryResponse(
                id=match.id,
                pet1_id=match.pet1_id,
                pet2_id=match.pet2_id,
                created_at=match.created_at,
                your_pet_id=your_pet_id,
                other_pet=PetPublicResponse.model_validate(other_pet),
            )
        )

    return summaries


@router.get("/relationship/{target_pet_id}", response_model=PetRelationshipResponse)
async def get_pet_relationship(
    target_pet_id: uuid.UUID,
    pet_id: uuid.UUID | None = Query(
        default=None, description="Which of your pets to check as; defaults to all of them"
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Where the caller already stands with `target_pet_id`, per pet.

    Browse surfaces (Community, pet detail) need this to stop offering
    "Interested" on a pet that is already matched or already swiped on — the
    swipe endpoint rejects those with a 400, which read as a broken button.

    The per-pet breakdown exists because "Interested" is an action taken *by a
    pet*, not by an account. An owner with two dogs has to be able to say which
    one is interested, and to see that one of them already asked.
    """
    own_pets_result = await db.execute(
        select(PetProfile).where(PetProfile.user_id == user.id)
    )
    own_pets = list(own_pets_result.scalars().all())
    own_pet_ids = [p.id for p in own_pets]

    if target_pet_id in own_pet_ids:
        return PetRelationshipResponse(pet_id=target_pet_id, status="own")

    if pet_id is not None:
        if pet_id not in own_pet_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pet does not belong to you",
            )
        own_pets = [p for p in own_pets if p.id == pet_id]

    target_result = await db.execute(
        select(PetProfile).where(PetProfile.id == target_pet_id)
    )
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

    # Only same-species pets can ever act on this target, so anything else would
    # be an option the swipe endpoint is guaranteed to refuse.
    candidates = [p for p in own_pets if p.species == target.species]
    if not candidates:
        return PetRelationshipResponse(pet_id=target_pet_id, status="no_pet")

    candidate_ids = [p.id for p in candidates]

    matches_result = await db.execute(
        select(Match).where(
            Match.deleted_at.is_(None),
            or_(
                and_(Match.pet1_id.in_(candidate_ids), Match.pet2_id == target_pet_id),
                and_(Match.pet2_id.in_(candidate_ids), Match.pet1_id == target_pet_id),
            ),
        )
    )
    candidate_id_set = set(candidate_ids)
    match_by_pet: dict[uuid.UUID, Match] = {}
    for match in matches_result.scalars().all():
        owner_side = match.pet1_id if match.pet1_id in candidate_id_set else match.pet2_id
        match_by_pet[owner_side] = match

    swipes_result = await db.execute(
        select(Swipe).where(
            Swipe.swiper_pet_id.in_(candidate_ids),
            Swipe.target_pet_id == target_pet_id,
            Swipe.is_undone.is_(False),
        )
    )
    swipe_by_pet = {s.swiper_pet_id: s for s in swipes_result.scalars().all()}

    favorites_result = await db.execute(
        select(Favorite).where(
            Favorite.pet_id.in_(candidate_ids),
            Favorite.target_pet_id == target_pet_id,
            Favorite.deleted_at.is_(None),
        )
    )
    favorite_by_pet = {f.pet_id: f for f in favorites_result.scalars().all()}

    entries: list[PetRelationshipEntry] = []
    for pet in candidates:
        match = match_by_pet.get(pet.id)
        if match is not None:
            entry_status, match_id = "matched", match.id
        else:
            swipe = swipe_by_pet.get(pet.id)
            match_id = None
            if swipe is None:
                entry_status = "none"
            elif swipe.action == SwipeAction.SKIP:
                entry_status = "skipped"
            else:
                entry_status = "liked"
        favorite = favorite_by_pet.get(pet.id)
        entries.append(
            PetRelationshipEntry(
                pet_id=pet.id,
                name=pet.name,
                primary_photo_url=pet.primary_photo_url,
                is_active=pet.is_active,
                status=entry_status,
                match_id=match_id,
                is_favorite=favorite is not None,
                favorite_id=favorite.id if favorite else None,
            )
        )

    # Summary for callers that only need one answer: a live match outranks a
    # pending like, which outranks a pass.
    for wanted in ("matched", "liked", "skipped"):
        hit = next((e for e in entries if e.status == wanted), None)
        if hit is not None:
            return PetRelationshipResponse(
                pet_id=target_pet_id,
                status=wanted,
                match_id=hit.match_id,
                your_pet_id=hit.pet_id,
                pets=entries,
            )

    return PetRelationshipResponse(pet_id=target_pet_id, status="none", pets=entries)


@router.post("/{match_id}/unmatch", response_model=UnmatchResponse)
async def unmatch(
    match_id: uuid.UUID,
    body: UnmatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Leave a match — removes it from both sides' Matches/Chat lists.

    No notification is sent to the other user on a plain unmatch (matches how
    most matching apps handle this — unmatching isn't meant to be a callout).
    Optionally also blocks the other user, which additionally soft-deletes
    every other active match between the two of you, same as POST /blocks.
    """
    match_result = await db.execute(
        select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    )
    match = match_result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_([match.pet1_id, match.pet2_id]))
    )
    pets = {pet.id: pet for pet in pets_result.scalars().all()}
    your_pet = next((p for p in pets.values() if p.user_id == user.id), None)
    if your_pet is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not part of this match")

    other_pet = pets[match.pet1_id] if your_pet.id == match.pet2_id else pets[match.pet2_id]
    other_user_id = other_pet.user_id

    now = datetime.now(timezone.utc)
    match.deleted_at = now

    if not body.block_user:
        # Plain unmatch means "not right now", not "never again", so the two
        # pets go back to being discoverable to each other. The swipes that
        # produced the match are what stopped that: browse and Discover both
        # hide anyone you have already swiped on, so an unmatched pet stayed
        # invisible in the deck for good, and the Community button behind it
        # could only ever return "Already swiped on this pet". Clearing both
        # directions puts the pair back to never having met.
        #
        # Blocking deliberately does not do this — those swipes stay, and the
        # block filter keeps them out of each other's browse entirely.
        await db.execute(
            delete(Swipe).where(
                or_(
                    and_(Swipe.swiper_pet_id == your_pet.id, Swipe.target_pet_id == other_pet.id),
                    and_(Swipe.swiper_pet_id == other_pet.id, Swipe.target_pet_id == your_pet.id),
                )
            )
        )

    if body.block_user:
        existing_block_result = await db.execute(
            select(Block).where(
                Block.blocking_user_id == user.id,
                Block.blocked_user_id == other_user_id,
            )
        )
        if existing_block_result.scalar_one_or_none() is None:
            # Same sweep as POST /blocks: blocking removes every match between
            # the two of you, not just the one being unmatched from here.
            other_pets_result = await db.execute(
                select(PetProfile.id).where(PetProfile.user_id == other_user_id)
            )
            other_pet_ids = [row[0] for row in other_pets_result.all()]
            your_pets_result = await db.execute(
                select(PetProfile.id).where(PetProfile.user_id == user.id)
            )
            your_pet_ids = [row[0] for row in your_pets_result.all()]

            if other_pet_ids and your_pet_ids:
                other_matches_result = await db.execute(
                    select(Match).where(
                        Match.deleted_at.is_(None),
                        or_(
                            and_(Match.pet1_id.in_(your_pet_ids), Match.pet2_id.in_(other_pet_ids)),
                            and_(Match.pet1_id.in_(other_pet_ids), Match.pet2_id.in_(your_pet_ids)),
                        ),
                    )
                )
                for other_match in other_matches_result.scalars().all():
                    other_match.deleted_at = now

            db.add(Block(blocking_user_id=user.id, blocked_user_id=other_user_id))

    await db.commit()

    if body.block_user:
        await cache_block(redis, str(user.id), str(other_user_id))

    return UnmatchResponse(
        message=f"Unmatched from {other_pet.name}" + (" and blocked" if body.block_user else ""),
        match_id=match.id,
        blocked=body.block_user,
        notification_sent=False,
    )


@router.get("/likes-received")
async def get_likes_received(
    pet_id: uuid.UUID = Query(description="Your pet ID to check likes for"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get pets that have liked your pet (but you haven't swiped on them yet).
    This shows potential matches waiting for your swipe.
    """
    
    # Verify pet belongs to user
    pet_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == pet_id,
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
    )
    pet = pet_result.scalar_one_or_none()
    
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your pet not found or inactive",
        )
    
    # Find pets that liked us (ordinary like or Super Woof)
    likes_result = await db.execute(
        select(Swipe.swiper_pet_id)
        .where(
            Swipe.target_pet_id == pet_id,
            Swipe.action.in_([SwipeAction.LIKE, SwipeAction.SUPER_LIKE]),
        )
    )
    liker_pet_ids = [row[0] for row in likes_result.all()]
    
    if not liker_pet_ids:
        return {"pets": [], "total": 0}
    
    # Find which ones we haven't swiped on yet
    already_swiped = await db.execute(
        select(Swipe.target_pet_id).where(
            Swipe.swiper_pet_id == pet_id,
            Swipe.target_pet_id.in_(liker_pet_ids),
        )
    )
    already_swiped_ids = {row[0] for row in already_swiped.all()}
    
    # Filter out already swiped
    pending_liker_ids = [pid for pid in liker_pet_ids if pid not in already_swiped_ids]
    
    if not pending_liker_ids:
        return {"pets": [], "total": 0}
    
    # Get pet details
    pets_result = await db.execute(
        select(PetProfile)
        .where(
            PetProfile.id.in_(pending_liker_ids),
            PetProfile.is_active.is_(True),
        )
        .order_by(PetProfile.created_at.desc())
    )
    
    pets = pets_result.scalars().all()
    
    # Fetch owner info for all pets
    user_ids = [p.user_id for p in pets]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}
    
    # Build response with owner info
    pets_with_owner = []
    for p in pets:
        pet_dict = PetPublicResponse.model_validate(p).model_dump()
        pet_dict["owner"] = users_map.get(p.user_id)
        pets_with_owner.append(PetPublicResponse.model_validate(pet_dict))
    
    return {
        "pets": pets_with_owner,
        "total": len(pets),
    }


@router.get("/notifications", response_model=list[NotificationWithDetails])
async def get_notifications(
    unread_only: bool = Query(default=False, description="Only show unread notifications"),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user's notifications with pet details.
    """
    
    filters = [Notification.user_id == user.id]
    if unread_only:
        filters.append(Notification.is_read.is_(False))
    
    notifications_result = await db.execute(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    
    notifications = notifications_result.scalars().all()
    
    if not notifications:
        return []
    
    # Get all related pet IDs
    pet_ids = set()
    for notif in notifications:
        pet_ids.add(notif.pet_id)
        pet_ids.add(notif.related_pet_id)
    
    # Fetch all pets
    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_(pet_ids))
    )
    pets_map = {pet.id: pet for pet in pets_result.scalars().all()}
    
    # Build response with details
    result = []
    for notif in notifications:
        your_pet = pets_map.get(notif.pet_id)
        other_pet = pets_map.get(notif.related_pet_id)
        
        if not your_pet or not other_pet:
            continue
        
        result.append(
            NotificationWithDetails(
                id=notif.id,
                notification_type=notif.notification_type.value,
                message=notif.message,
                is_read=notif.is_read,
                is_super=notif.is_super,
                created_at=notif.created_at,
                read_at=notif.read_at,
                your_pet={
                    "id": str(your_pet.id),
                    "name": your_pet.name,
                    "primary_photo_url": your_pet.primary_photo_url,
                },
                other_pet={
                    "id": str(other_pet.id),
                    "name": other_pet.name,
                    "primary_photo_url": other_pet.primary_photo_url,
                },
                match_id=notif.match_id,
            )
        )
    
    return result


@router.patch("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_read(
    body: MarkNotificationReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark notifications as read.
    """
    
    if not body.notification_ids:
        return
    
    # Update notifications that belong to this user
    result = await db.execute(
        select(Notification).where(
            Notification.id.in_(body.notification_ids),
            Notification.user_id == user.id,
        )
    )
    
    notifications = result.scalars().all()
    now = datetime.now(timezone.utc)
    
    for notif in notifications:
        notif.is_read = True
        notif.read_at = now

    await db.commit()


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark every unread notification read in one go, without the caller
    needing to first fetch and pass every id."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    )
    now = datetime.now(timezone.utc)
    for notif in result.scalars().all():
        notif.is_read = True
        notif.read_at = now

    await db.commit()


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a single notification permanently (not just mark it read)."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    await db.delete(notification)
    await db.commit()


@router.delete("/notifications", status_code=status.HTTP_204_NO_CONTENT)
async def clear_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear every notification for the caller — a full reset, not scoped to
    read/unread, matching what a "Clear all" button implies."""
    await db.execute(delete(Notification).where(Notification.user_id == user.id))
    await db.commit()


@router.get("/swipe-history", response_model=SwipeHistoryResponse)
async def get_swipe_history(
    pet_id: uuid.UUID = Query(description="Your pet ID"),
    action: str | None = Query(default=None, description="Filter by action: like or skip"),
    breed: str | None = Query(default=None, description="Filter by target pet breed (case-insensitive contains)"),
    date_from: str | None = Query(default=None, description="ISO date YYYY-MM-DD — start of range"),
    date_to: str | None = Query(default=None, description="ISO date YYYY-MM-DD — end of range"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the swipe history for your pet — see who you've liked or skipped.

    Supports filtering by action, breed, date range, and pagination via limit/offset.
    Only non-undone swipes are returned.
    """

    # Verify pet belongs to user
    pet_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == pet_id,
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
    )
    pet = pet_result.scalar_one_or_none()

    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your pet not found or inactive",
        )

    # Base filters — always exclude undone swipes
    filters = [
        Swipe.swiper_pet_id == pet_id,
        Swipe.is_undone == False,  # noqa: E712
    ]

    if action:
        if action not in ["like", "skip"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action. Must be 'like' or 'skip'",
            )
        filters.append(Swipe.action == SwipeAction(action))

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from must be in YYYY-MM-DD format",
            )
        filters.append(Swipe.created_at >= dt_from)

    if date_to:
        try:
            # Include the full end day by pushing to the next day
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_to must be in YYYY-MM-DD format",
            )
        filters.append(Swipe.created_at < dt_to)

    # If breed filter is requested, resolve the matching pet IDs first
    if breed:
        breed_pets_result = await db.execute(
            select(PetProfile.id).where(
                PetProfile.breed.ilike(f"%{breed}%")
            )
        )
        breed_pet_ids = [row[0] for row in breed_pets_result.all()]
        if not breed_pet_ids:
            return SwipeHistoryResponse(swipes=[], total=0, limit=limit, offset=offset)
        filters.append(Swipe.target_pet_id.in_(breed_pet_ids))

    # Count query for total
    count_result = await db.execute(
        select(func.count()).select_from(Swipe).where(*filters)
    )
    total = count_result.scalar_one()

    # Paginated fetch
    swipes_result = await db.execute(
        select(Swipe)
        .where(*filters)
        .order_by(Swipe.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    swipes = swipes_result.scalars().all()

    if not swipes:
        return SwipeHistoryResponse(swipes=[], total=total, limit=limit, offset=offset)

    # Get target pet details (eager-load owner so PetPublicResponse.model_validate
    # below can read target_pet.owner without an async lazy-load)
    target_pet_ids = [s.target_pet_id for s in swipes]
    pets_result = await db.execute(
        select(PetProfile).options(selectinload(PetProfile.user)).where(PetProfile.id.in_(target_pet_ids))
    )
    pets_map = {p.id: p for p in pets_result.scalars().all()}

    history_items: list[SwipeHistoryItem] = []
    for swipe in swipes:
        target_pet = pets_map.get(swipe.target_pet_id)
        if target_pet:
            pet_dict = PetPublicResponse.model_validate(target_pet).model_dump()
            history_items.append(
                SwipeHistoryItem(
                    swipe_id=swipe.id,
                    action=swipe.action.value,
                    created_at=swipe.created_at,
                    target_pet=pet_dict,
                )
            )

    return SwipeHistoryResponse(
        swipes=history_items,
        total=total,
        limit=limit,
        offset=offset,
    )



@router.post("/likes/{notification_id}/accept")
async def accept_like(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a like notification - creates a match between the two pets.
    """
    
    # Get the notification
    notif_result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.notification_type == NotificationType.NEW_LIKE,
        )
    )
    notification = notif_result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Like notification not found",
        )
    
    # Check if a live match already exists
    pet1_id, pet2_id = sorted([notification.pet_id, notification.related_pet_id])
    existing_match = await db.execute(
        select(Match).where(
            Match.pet1_id == pet1_id,
            Match.pet2_id == pet2_id,
            Match.deleted_at.is_(None),
        )
    )

    if existing_match.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match already exists",
        )
    
    # Get both pets for names
    pets_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id.in_([notification.pet_id, notification.related_pet_id])
        )
    )
    pets = {pet.id: pet for pet in pets_result.scalars().all()}
    your_pet = pets.get(notification.pet_id)
    other_pet = pets.get(notification.related_pet_id)
    
    if not your_pet or not other_pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both pets not found",
        )
    
    # Create the match, or revive the pair's existing row if they had matched
    # and unmatched before — uq_match_pair ignores deleted_at, so a plain insert
    # raises IntegrityError for any pair with history.
    match, _ = await _open_match(db, notification.pet_id, notification.related_pet_id)
    
    # Create match notifications for BOTH users
    # Notification for you (acceptor)
    your_match_notif = Notification(
        user_id=user.id,
        notification_type=NotificationType.NEW_MATCH,
        pet_id=notification.pet_id,
        related_pet_id=notification.related_pet_id,
        match_id=match.id,
        message=f"It's a match! {your_pet.name} accepted {other_pet.name}'s interest!",
    )
    db.add(your_match_notif)
    
    # Notification for other user (original liker)
    other_match_notif = Notification(
        user_id=other_pet.user_id,
        notification_type=NotificationType.NEW_MATCH,
        pet_id=notification.related_pet_id,
        related_pet_id=notification.pet_id,
        match_id=match.id,
        message=f"Great news! {your_pet.name} accepted {other_pet.name}'s interest!",
    )
    db.add(other_match_notif)
    
    # Mark the original like notification as read
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)

    # Record the acceptance as a swipe from your pet onto theirs.
    #
    # Accepting is a "like" in every sense except that it never went through
    # POST /swipe, so no Swipe row existed for this direction. Browse, Discover
    # and "likes you" all decide what to show from the Swipe table, so a pet you
    # had *just matched with* kept coming back as an un-swiped candidate with an
    # "Interested" button that could only ever 400 with "Already swiped on this
    # pet". reject_like already writes its SKIP for exactly this reason; accept
    # was the half that got missed. An existing SKIP (rejected, then accepted
    # from the same notification) is upgraded rather than duplicated — the
    # (swiper, target) pair is unique.
    reciprocal_result = await db.execute(
        select(Swipe).where(
            Swipe.swiper_pet_id == notification.pet_id,
            Swipe.target_pet_id == notification.related_pet_id,
        )
    )
    reciprocal = reciprocal_result.scalar_one_or_none()
    if reciprocal is None:
        db.add(
            Swipe(
                swiper_pet_id=notification.pet_id,
                target_pet_id=notification.related_pet_id,
                action=SwipeAction.LIKE,
            )
        )
    else:
        reciprocal.action = SwipeAction.LIKE
        reciprocal.is_undone = False
        reciprocal.undone_at = None

    await db.commit()
    await db.refresh(match)
    await db.refresh(your_match_notif)
    await db.refresh(other_match_notif)
    await _push_notification(your_match_notif, other_pet)
    await _push_notification(other_match_notif, your_pet)

    # Grant achievements for both users
    from app.models.user_achievement import AchievementType
    from app.services import achievements
    from sqlalchemy import func
    
    # Count matches for both users
    for owner_id in [user.id, other_pet.user_id]:
        # Count total matches for this user
        owner_pets_result = await db.execute(
            select(PetProfile.id).where(PetProfile.user_id == owner_id)
        )
        owner_pet_ids = [row[0] for row in owner_pets_result.all()]
        
        if owner_pet_ids:
            match_count_result = await db.execute(
                select(func.count())
                .select_from(Match)
                .where(
                    or_(
                        Match.pet1_id.in_(owner_pet_ids),
                        Match.pet2_id.in_(owner_pet_ids),
                    )
                )
            )
            match_count = match_count_result.scalar_one()
            
            # Grant first match achievement
            if match_count == 1:
                await achievements.grant_achievement(db, owner_id, AchievementType.FIRST_MATCH)
            # Grant five matches achievement
            elif match_count == 5:
                await achievements.grant_achievement(db, owner_id, AchievementType.FIVE_MATCHES)
    
    return {
        "match_id": str(match.id),
        "message": f"Match created! You can now chat with {other_pet.name}'s owner.",
    }


@router.post("/likes/{notification_id}/reject")
async def reject_like(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a like notification - no match is created.
    """
    
    # Get the notification
    notif_result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.notification_type == NotificationType.NEW_LIKE,
        )
    )
    notification = notif_result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Like notification not found",
        )
    
    # Just mark as read, no match created
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)

    # Record a SKIP so this pet stops resurfacing in "likes you" — without
    # this, rejecting only dismissed the notification. /likes-received and
    # /browse both filter on the Swipe table, not Notification, so the same
    # pet kept coming back every time the list was refetched.
    existing_swipe = await db.execute(
        select(Swipe).where(
            Swipe.swiper_pet_id == notification.pet_id,
            Swipe.target_pet_id == notification.related_pet_id,
        )
    )
    if existing_swipe.scalar_one_or_none() is None:
        db.add(
            Swipe(
                swiper_pet_id=notification.pet_id,
                target_pet_id=notification.related_pet_id,
                action=SwipeAction.SKIP,
            )
        )

    await db.commit()

    return {
        "message": "Like rejected. No match created.",
    }


@router.post("/undo-swipe", response_model=UndoSwipeResponse)
async def undo_swipe(
    body: UndoSwipeRequest,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """
    Undo a previous swipe within the 5-minute window.

    - 404 if swipe not found
    - 403 if swiper pet does not belong to the current user
    - 400 if already undone
    - 400 if the 5-minute undo window has expired
    - 400 if the resulting match has messages (cannot undo with message history)
    - Soft-deletes the match if one exists and has no messages
    """

    # 1. Fetch the swipe
    swipe_result = await db.execute(
        select(Swipe).where(Swipe.id == body.swipe_id)
    )
    swipe = swipe_result.scalar_one_or_none()

    if swipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Swipe not found",
        )

    # 2. Verify ownership — swiper pet must belong to the current user
    pet_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == swipe.swiper_pet_id,
            PetProfile.user_id == current_user.id,
        )
    )
    if pet_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own the pet that performed this swipe",
        )

    # 3. Already undone?
    if swipe.is_undone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Swipe already undone",
        )

    # 4. Time-window check (5 minutes = 300 seconds)
    now = datetime.now(timezone.utc)
    swipe_age = (now - swipe.created_at).total_seconds()
    if swipe_age > 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Undo window expired (5 minutes)",
        )

    # 5. Look for an active match between swiper_pet and target_pet
    swiper_id = swipe.swiper_pet_id
    target_id = swipe.target_pet_id
    pet1_id, pet2_id = sorted([swiper_id, target_id])

    match_result = await db.execute(
        select(Match).where(
            Match.pet1_id == pet1_id,
            Match.pet2_id == pet2_id,
            Match.deleted_at.is_(None),
        )
    )
    match = match_result.scalar_one_or_none()

    # 6. If a match exists, check for messages
    if match is not None:
        from app.models.message import Message

        msg_count_result = await db.execute(
            select(Message).where(
                Message.match_id == match.id,
                Message.deleted_at.is_(None),
            )
        )
        messages = msg_count_result.scalars().all()
        if len(messages) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot undo: messages exist in this match",
            )

    # Charge the daily undo allowance only now that every check above has
    # passed — same reasoning as the Super Woof and report/block/favorite
    # fixes earlier in this sweep: a Depends()-based rate limiter runs
    # before the route body, so it used to charge even for a swipe_id that
    # didn't exist, wasn't yours, was already undone, or was outside the
    # 5-minute window — none of which actually attempt an undo.
    await check_rate_limit(
        redis=redis,
        user_id=str(current_user.id),
        key_prefix="undo",
        limit=10,
        window=3600,
    )

    # 7. Apply changes in a single transaction
    swipe.is_undone = True
    swipe.undone_at = now

    match_was_deleted = False
    if match is not None:
        match.deleted_at = now
        match_was_deleted = True

    await db.commit()

    # 8. Build response
    return UndoSwipeResponse(
        message="Swipe undone successfully",
        swipe_id=swipe.id,
        action_taken="match_deleted" if match_was_deleted else "swipe_reverted",
    )


@router.get("/statistics", response_model=SwipeStatisticsResponse)
async def get_swipe_statistics(
    pet_id: uuid.UUID = Query(description="Your pet ID to fetch statistics for"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated swipe statistics for a pet.

    Returns:
    - Total likes and skips sent
    - Like-to-skip ratio
    - Number of matches created
    - Swipe activity for the last 30 days (per-day breakdown)
    - Top 3 breeds liked
    - Average response time (reserved for future implementation)
    """

    # 1. Verify pet belongs to the authenticated user
    pet_result = await db.execute(
        select(PetProfile).where(
            PetProfile.id == pet_id,
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
    )
    pet = pet_result.scalar_one_or_none()
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pet not found or does not belong to you",
        )

    # 2. Total likes
    likes_result = await db.execute(
        select(func.count()).select_from(Swipe).where(
            Swipe.swiper_pet_id == pet_id,
            Swipe.action == SwipeAction.LIKE,
            Swipe.is_undone == False,  # noqa: E712
        )
    )
    total_likes: int = likes_result.scalar_one()

    # 3. Total skips
    skips_result = await db.execute(
        select(func.count()).select_from(Swipe).where(
            Swipe.swiper_pet_id == pet_id,
            Swipe.action == SwipeAction.SKIP,
            Swipe.is_undone == False,  # noqa: E712
        )
    )
    total_skips: int = skips_result.scalar_one()

    # 4. Like-to-skip ratio
    if total_skips > 0:
        like_to_skip_ratio = total_likes / total_skips
    else:
        like_to_skip_ratio = float(total_likes)

    # 5. Matches created (not soft-deleted)
    matches_result = await db.execute(
        select(func.count()).select_from(Match).where(
            or_(Match.pet1_id == pet_id, Match.pet2_id == pet_id),
            Match.deleted_at.is_(None),
        )
    )
    matches_created: int = matches_result.scalar_one()

    # 6. Last 30 days — Python-side aggregation
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_swipes_result = await db.execute(
        select(Swipe).where(
            Swipe.swiper_pet_id == pet_id,
            Swipe.is_undone == False,  # noqa: E712
            Swipe.created_at >= thirty_days_ago,
        )
    )
    recent_swipes = recent_swipes_result.scalars().all()

    daily_map: dict[str, dict[str, int]] = {}
    for swipe in recent_swipes:
        # Normalise to UTC date string
        swipe_date = swipe.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if swipe_date not in daily_map:
            daily_map[swipe_date] = {"likes": 0, "skips": 0}
        if swipe.action == SwipeAction.LIKE:
            daily_map[swipe_date]["likes"] += 1
        else:
            daily_map[swipe_date]["skips"] += 1

    last_30_days = [
        DailySwipeStats(date=date_str, likes=counts["likes"], skips=counts["skips"])
        for date_str, counts in sorted(daily_map.items())
    ]

    # 7. Top breeds liked — Python-side groupby
    liked_swipes_result = await db.execute(
        select(Swipe.target_pet_id).where(
            Swipe.swiper_pet_id == pet_id,
            Swipe.action == SwipeAction.LIKE,
            Swipe.is_undone == False,  # noqa: E712
        )
    )
    liked_target_ids = [row[0] for row in liked_swipes_result.all()]

    top_breeds: list[TopBreed] = []
    if liked_target_ids:
        target_pets_result = await db.execute(
            select(PetProfile.breed).where(PetProfile.id.in_(liked_target_ids))
        )
        breed_counts: dict[str, int] = {}
        for (breed_name,) in target_pets_result.all():
            if breed_name:
                breed_counts[breed_name] = breed_counts.get(breed_name, 0) + 1

        top_breeds = [
            TopBreed(breed=breed_name, count=count)
            for breed_name, count in sorted(breed_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

    # 8. Average response time — deferred (complex calculation)
    avg_response_time_minutes: float | None = None

    return SwipeStatisticsResponse(
        pet_id=pet_id,
        total_likes=total_likes,
        total_skips=total_skips,
        like_to_skip_ratio=like_to_skip_ratio,
        matches_created=matches_created,
        avg_response_time_minutes=avg_response_time_minutes,
        last_30_days=last_30_days,
        top_breeds_liked=top_breeds,
    )


@router.get("/browse", response_model=BrowsePetsResponse)
async def browse_pets(
    pet_id: uuid.UUID | None = Query(default=None, description="Your pet ID doing the browsing (optional for simple browse)"),
    radius: float = Query(default=5000, ge=1, le=5000, description="Search radius in km (default: 5000 = show all)"),
    species: str | None = Query(default=None, description="Filter by species"),
    breed: str | None = Query(default=None, description="Filter by breed (partial match)"),
    age_min: int | None = Query(default=None, ge=0, description="Minimum age in months"),
    age_max: int | None = Query(default=None, ge=0, description="Maximum age in months"),
    gender: str | None = Query(default=None, description="Filter by gender"),
    is_vaccinated: bool | None = Query(default=None, description="Filter by vaccination status"),
    is_neutered: bool | None = Query(default=None, description="Filter by neutered status"),
    is_trained: bool | None = Query(default=None, description="Filter by training status"),
    limit: int = Query(default=50, ge=1, le=50, description="Max results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Browse pet candidates within a distance radius.

    Returns active pets within `radius` km, sorted by distance ascending.
    If no pet_id provided, shows all pets without filtering by swipes.
    Supports optional filtering by species, breed, age range, gender, and health attributes.
    """

    # 1. Verify pet_id belongs to current_user and is active (if provided)
    my_pet = None
    own_pet_ids = []
    swiped_ids = set()
    
    if pet_id:
        pet_result = await db.execute(
            select(PetProfile).where(
                PetProfile.id == pet_id,
                PetProfile.user_id == current_user.id,
                PetProfile.is_active.is_(True),
            )
        )
        my_pet = pet_result.scalar_one_or_none()
        if my_pet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pet not found or inactive",
            )
        
        # 4. Collect all pet IDs owned by the current user (for exclusion)
        own_pets_result = await db.execute(
            select(PetProfile.id).where(PetProfile.user_id == current_user.id)
        )
        own_pet_ids = [row[0] for row in own_pets_result.all()]

        # 5. Collect all pet IDs this pet has already swiped on
        swiped_result = await db.execute(
            select(Swipe.target_pet_id).where(Swipe.swiper_pet_id == pet_id)
        )
        swiped_ids = {row[0] for row in swiped_result.all()}

        # ...plus everyone this pet is already matched with. Normally the swipe
        # that led to the match covers this, but a match made by *accepting* a
        # like historically left no swipe row on the acceptor's side, so their
        # own matches kept resurfacing in the deck. Reading the Match table too
        # makes this correct for those existing rows without a backfill.
        matched_result = await db.execute(
            select(Match.pet1_id, Match.pet2_id).where(
                Match.deleted_at.is_(None),
                or_(Match.pet1_id == pet_id, Match.pet2_id == pet_id),
            )
        )
        for pet1_id, pet2_id in matched_result.all():
            swiped_ids.add(pet2_id if pet1_id == pet_id else pet1_id)

    # 2. User location is optional now
    user_lat = current_user.latitude
    user_lng = current_user.longitude
    has_location = user_lat is not None and user_lng is not None

    # 6. Build candidate query
    filters = [
        PetProfile.is_active.is_(True),
        # Always, not just when a pet_id was passed. Without a pet_id this used
        # to deal the caller their own pets into their own swipe deck.
        PetProfile.user_id != current_user.id,
    ]

    if my_pet is not None:
        # Only same-species pets can be matched with — POST /swipe rejects
        # anything else outright. Leaving them in the deck produced a stack of
        # cards where every like and Super Woof came back a 400: the card was
        # optimistically removed, the error put it straight back at the front,
        # and the same handful of pets cycled forever.
        filters.append(PetProfile.species == my_pet.species)

    if swiped_ids:
        filters.append(PetProfile.id.notin_(swiped_ids))

    if species is not None:
        filters.append(PetProfile.species == species)

    if breed is not None:
        filters.append(PetProfile.breed.ilike(f"%{breed}%"))

    if age_min is not None:
        filters.append(PetProfile.age_months >= age_min)

    if age_max is not None:
        filters.append(PetProfile.age_months <= age_max)

    if gender is not None:
        filters.append(PetProfile.gender == gender)

    if is_vaccinated is not None:
        filters.append(PetProfile.is_vaccinated == is_vaccinated)

    if is_neutered is not None:
        filters.append(PetProfile.is_neutered == is_neutered)

    if is_trained is not None:
        filters.append(PetProfile.is_trained == is_trained)

    # Cap the pool well above the page size and order it deterministically. The
    # old hard .limit(50) was applied *before* distance filtering and scoring, so
    # it silently truncated the catalogue and then ranked whatever survived —
    # pets beyond the first 50 rows were unreachable no matter how compatible.
    candidates_result = await db.execute(
        select(PetProfile)
        .options(selectinload(PetProfile.user))
        .where(*filters)
        .order_by(PetProfile.created_at.desc(), PetProfile.id)
        .limit(CANDIDATE_POOL_SIZE)
    )
    candidates = candidates_result.scalars().all()

    if not candidates:
        filters_applied = {
            "radius_km": radius,
            "species": species,
            "breed": breed,
            "age_min": age_min,
            "age_max": age_max,
            "gender": gender,
            "is_vaccinated": is_vaccinated,
            "is_neutered": is_neutered,
            "is_trained": is_trained,
        }
        return BrowsePetsResponse(candidates=[], total=0, filters_applied=filters_applied)

    # 7. Fetch owners' coordinates and compute distances
    owner_ids = list({c.user_id for c in candidates})
    owners_result = await db.execute(select(User).where(User.id.in_(owner_ids)))
    owners_map: dict = {u.id: u for u in owners_result.scalars().all()}

    # Distance is None when it genuinely can't be computed — either the caller
    # or the candidate's owner has no coordinates. Those pets are kept and
    # ranked last instead of being dropped: an owner who skipped the location
    # step was invisible to every located user, which is a large silent hole in
    # a deck people already complain is too short.
    nearby: list[tuple[PetProfile, float | None]] = []

    for pet in candidates:
        owner = owners_map.get(pet.user_id)
        if owner is None:
            continue
        if has_location and owner.latitude is not None and owner.longitude is not None:
            dist = haversine_distance(user_lat, user_lng, owner.latitude, owner.longitude)
            if dist > radius:
                continue
            nearby.append((pet, dist))
        else:
            nearby.append((pet, None))

    # 8. Score + rank. With a pet_id, rank by compatibility (breed/distance/age/
    # gender preference) instead of plain distance — same scoring engine used
    # nowhere else yet. Without one (anonymous/simple browse) fall back to
    # distance ascending, same as before.
    scores: dict[uuid.UUID, int] = {}
    if my_pet is not None:
        prefs_result = await db.execute(
            select(MatchPreference).where(MatchPreference.user_id == current_user.id)
        )
        preference = prefs_result.scalar_one_or_none()
        user_preferences = (
            {"preferred_gender": preference.preferred_gender} if preference else None
        )
        for pet, dist in nearby:
            # An unknown distance scores as "far" rather than crashing the
            # comparison chain inside the scorer.
            score, _breakdown = calculate_match_score(
                my_pet, pet, UNKNOWN_DISTANCE_KM if dist is None else dist, user_preferences
            )
            scores[pet.id] = score

    # Rank by compatibility when browsing as a pet, by distance otherwise, and
    # break ties on the pet's id. Sorting on the score (or the distance) alone
    # left equally-ranked pets in whatever order the database happened to return
    # them, so the deck appeared to reshuffle itself on every refetch. Pets with
    # no known distance sort last in both modes.
    if my_pet is not None:
        nearby.sort(
            key=lambda x: (
                -scores[x[0].id],
                UNKNOWN_DISTANCE_KM if x[1] is None else x[1],
                str(x[0].id),
            )
        )
    else:
        nearby.sort(key=lambda x: (UNKNOWN_DISTANCE_KM if x[1] is None else x[1], str(x[0].id)))

    # Apply limit after ranking
    nearby = nearby[:limit]

    # 9. Build response candidates
    now_utc = datetime.now(timezone.utc)
    response_candidates: list[MatchCandidateResponse] = []
    for pet, dist in nearby:
        pet_dict = PetPublicResponse.model_validate(pet).model_dump()
        response_candidates.append(
            MatchCandidateResponse(
                pet=pet_dict,
                distance_km=None if dist is None else round(dist, 2),
                calculated_at=now_utc,
                compatibility_score=scores.get(pet.id),
            )
        )

    # 10. Build filters_applied
    filters_applied = {
        "radius_km": radius,
        "species": species,
        "breed": breed,
        "age_min": age_min,
        "age_max": age_max,
        "gender": gender,
        "is_vaccinated": is_vaccinated,
        "is_neutered": is_neutered,
        "is_trained": is_trained,
    }

    # 11. Return response
    return BrowsePetsResponse(
        candidates=response_candidates,
        total=len(response_candidates),
        filters_applied=filters_applied,
    )


@router.get("/breeds", response_model=list[str])
async def get_all_breeds(
    species: str | None = Query(default=None, description="Filter breeds by species"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all unique breeds registered in the application.
    Optionally filter by species to get breed list for a specific animal type.
    Returns breeds sorted alphabetically.
    """
    query = select(PetProfile.breed).where(PetProfile.is_active.is_(True)).distinct()
    
    if species:
        query = query.where(PetProfile.species == species)
    
    result = await db.execute(query.order_by(PetProfile.breed))
    breeds = [row[0] for row in result.all()]
    
    return breeds
