import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import undo_rate_limit
from app.core.redis import get_redis
from app.models.favorite import Favorite
from app.models.block import Block
from app.models.match import Match
from app.models.notification import Notification, NotificationType
from app.models.pet_profile import PetProfile
from app.models.swipe import Swipe, SwipeAction
from app.models.user import User
from app.schemas.match import (
    MarkNotificationReadRequest,
    MatchResponse,
    NotificationResponse,
    NotificationWithDetails,
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
from app.utils.distance import haversine_distance

router = APIRouter(
    prefix="/matches",
    tags=["matches"],
)


@router.post("/swipe", response_model=SwipeResponse)
async def swipe_on_pet(
    body: SwipeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Swipe on a pet (like or skip).
    - Right swipe (like): Sends notification to target pet owner, they must accept/reject
    - Left swipe (skip): No notification sent
    
    Validates:
    - Both pets exist and are active
    - Swiper pet belongs to current user
    - Same species (dogs can only match with dogs, etc.)
    - Not swiping on your own pet
    - Haven't already swiped on this pet
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
    
    if not swiper_pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your pet not found or inactive",
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target pet not found or inactive",
        )
    
    # Can't swipe on your own pet
    if target_pet.user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot swipe on your own pet",
        )
    
    # Must be same species - inter-species matching not allowed
    if swiper_pet.species != target_pet.species:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Species mismatch: {swiper_pet.species} cannot match with {target_pet.species}",
        )
    
    # Check if already swiped on this pet
    existing_swipe = await db.execute(
        select(Swipe).where(
            Swipe.swiper_pet_id == body.pet_id,
            Swipe.target_pet_id == body.target_pet_id,
        )
    )
    if existing_swipe.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already swiped on this pet",
        )
    
    # Create the swipe
    swipe = Swipe(
        swiper_pet_id=body.pet_id,
        target_pet_id=body.target_pet_id,
        action=SwipeAction.LIKE if body.action == "like" else SwipeAction.SKIP,
    )
    db.add(swipe)
    
    # If it's a LIKE, send notification to target pet owner (no auto-match)
    if body.action == "like":
        # Send "NEW_LIKE" notification to target pet owner
        notification_target = Notification(
            user_id=target_pet.user_id,
            notification_type=NotificationType.NEW_LIKE,
            pet_id=body.target_pet_id,
            related_pet_id=body.pet_id,
            match_id=None,  # No match yet
            message=f"{swiper_pet.name} is interested in {target_pet.name}!",
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
    
    return SwipeResponse(
        swiper_pet_id=swipe.swiper_pet_id,
        target_pet_id=swipe.target_pet_id,
        action=swipe.action.value,
        is_match=False,  # No auto-match anymore
        match_id=None,
        created_at=swipe.created_at,
    )


@router.get("/my-matches", response_model=list[MatchResponse])
async def get_my_matches(
    pet_id: uuid.UUID | None = Query(default=None, description="Filter by specific pet"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all matches for the current user's pets.
    Optionally filter by a specific pet ID.
    """
    
    # Get user's pet IDs
    user_pets_result = await db.execute(
        select(PetProfile.id).where(
            PetProfile.user_id == user.id,
            PetProfile.is_active.is_(True),
        )
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
            )
        )
        .order_by(Match.created_at.desc())
    )
    
    matches = matches_result.scalars().all()
    return [MatchResponse.model_validate(m) for m in matches]


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
    
    # Find pets that liked us
    likes_result = await db.execute(
        select(Swipe.swiper_pet_id)
        .where(
            Swipe.target_pet_id == pet_id,
            Swipe.action == SwipeAction.LIKE,
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
    now = datetime.now()
    
    for notif in notifications:
        notif.is_read = True
        notif.read_at = now
    
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

    # Get target pet details
    target_pet_ids = [s.target_pet_id for s in swipes]
    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_(target_pet_ids))
    )
    pets_map = {p.id: p for p in pets_result.scalars().all()}

    # Fetch owner info for all pets
    user_ids = list({p.user_id for p in pets_map.values()})
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    history_items: list[SwipeHistoryItem] = []
    for swipe in swipes:
        target_pet = pets_map.get(swipe.target_pet_id)
        if target_pet:
            pet_dict = PetPublicResponse.model_validate(target_pet).model_dump()
            owner = users_map.get(target_pet.user_id)
            if owner:
                pet_dict["owner"] = owner
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
    
    # Check if match already exists
    pet1_id, pet2_id = sorted([notification.pet_id, notification.related_pet_id])
    existing_match = await db.execute(
        select(Match).where(
            Match.pet1_id == pet1_id,
            Match.pet2_id == pet2_id,
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
    
    # Create the match
    match = Match(
        pet1_id=pet1_id,
        pet2_id=pet2_id,
    )
    db.add(match)
    await db.flush()
    
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
    notification.read_at = datetime.now()
    
    await db.commit()
    await db.refresh(match)
    
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
    notification.read_at = datetime.now()
    
    await db.commit()
    
    return {
        "message": "Like rejected. No match created.",
    }


@router.post("/undo-swipe", response_model=UndoSwipeResponse)
async def undo_swipe(
    body: UndoSwipeRequest,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(undo_rate_limit),
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
    pet_id: uuid.UUID = Query(description="Your pet ID doing the browsing"),
    radius: float = Query(default=50, ge=1, le=500, description="Search radius in km"),
    species: str | None = Query(default=None, description="Filter by species"),
    age_min: int | None = Query(default=None, ge=0, description="Minimum age in months"),
    age_max: int | None = Query(default=None, ge=0, description="Maximum age in months"),
    gender: str | None = Query(default=None, description="Filter by gender"),
    limit: int = Query(default=50, ge=1, le=50, description="Max results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Browse pet candidates within a distance radius.

    Returns active pets within `radius` km, sorted by distance ascending.
    Excludes the caller's own pets and any pets already swiped on.
    Supports optional filtering by species, age range, and gender.
    """

    # 1. Verify pet_id belongs to current_user and is active
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

    # 2. Require the user's own coordinates
    if current_user.latitude is None or current_user.longitude is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location not set. Please update your profile with coordinates before using distance-based filtering",
        )

    user_lat = current_user.latitude
    user_lng = current_user.longitude

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

    # 6. Build candidate query
    filters = [
        PetProfile.is_active.is_(True),
        PetProfile.user_id != current_user.id,
    ]

    if swiped_ids:
        filters.append(PetProfile.id.notin_(swiped_ids))

    if species is not None:
        filters.append(PetProfile.species == species)

    if age_min is not None:
        filters.append(PetProfile.age_months >= age_min)

    if age_max is not None:
        filters.append(PetProfile.age_months <= age_max)

    if gender is not None:
        filters.append(PetProfile.gender == gender)

    candidates_result = await db.execute(
        select(PetProfile).where(*filters).limit(50)
    )
    candidates = candidates_result.scalars().all()

    if not candidates:
        filters_applied = {
            "radius_km": radius,
            "species": species,
            "age_min": age_min,
            "age_max": age_max,
            "gender": gender,
        }
        return BrowsePetsResponse(candidates=[], total=0, filters_applied=filters_applied)

    # 7. Fetch owners' coordinates and compute distances
    owner_ids = list({c.user_id for c in candidates})
    owners_result = await db.execute(select(User).where(User.id.in_(owner_ids)))
    owners_map: dict = {u.id: u for u in owners_result.scalars().all()}

    nearby: list[tuple[PetProfile, float]] = []
    for pet in candidates:
        owner = owners_map.get(pet.user_id)
        if owner is None or owner.latitude is None or owner.longitude is None:
            # Skip candidates whose owner has no location set
            continue
        dist = haversine_distance(user_lat, user_lng, owner.latitude, owner.longitude)
        if dist <= radius:
            nearby.append((pet, dist))

    # 8. Sort by distance ascending
    nearby.sort(key=lambda x: x[1])

    # Apply limit after distance filtering
    nearby = nearby[:limit]

    # 9. Build response candidates
    now_utc = datetime.now(timezone.utc)
    response_candidates: list[MatchCandidateResponse] = []
    for pet, dist in nearby:
        owner = owners_map[pet.user_id]
        pet_dict = PetPublicResponse.model_validate(pet).model_dump()
        pet_dict["owner"] = owner
        response_candidates.append(
            MatchCandidateResponse(
                pet=pet_dict,
                distance_km=round(dist, 2),
                calculated_at=now_utc,
            )
        )

    # 10. Build filters_applied
    filters_applied = {
        "radius_km": radius,
        "species": species,
        "age_min": age_min,
        "age_max": age_max,
        "gender": gender,
    }

    # 11. Return response
    return BrowsePetsResponse(
        candidates=response_candidates,
        total=len(response_candidates),
        filters_applied=filters_applied,
    )
