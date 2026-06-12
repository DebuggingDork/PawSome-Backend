import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
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
    - Right swipe (like): If target pet also liked you, creates a match
    - Left swipe (skip): No match, just records the swipe
    
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
    
    is_match = False
    match_id = None
    
    # If it's a LIKE, check for mutual match
    if body.action == "like":
        # Check if target pet also liked us
        mutual_like = await db.execute(
            select(Swipe).where(
                Swipe.swiper_pet_id == body.target_pet_id,
                Swipe.target_pet_id == body.pet_id,
                Swipe.action == SwipeAction.LIKE,
            )
        )
        
        if mutual_like.scalar_one_or_none():
            # It's a match! Create the match record
            is_match = True
            
            # Store pets in consistent order (smaller UUID first)
            pet1_id, pet2_id = sorted([body.pet_id, body.target_pet_id])
            
            match = Match(
                pet1_id=pet1_id,
                pet2_id=pet2_id,
            )
            db.add(match)
            await db.flush()  # Get the match ID
            match_id = match.id
            
            # Create notifications for BOTH users
            # Notification for current user
            notification_user = Notification(
                user_id=user.id,
                notification_type=NotificationType.NEW_MATCH,
                pet_id=body.pet_id,
                related_pet_id=body.target_pet_id,
                match_id=match_id,
                message=f"It's a match! {swiper_pet.name} and {target_pet.name} liked each other!",
            )
            db.add(notification_user)
            
            # Notification for target pet owner
            notification_target = Notification(
                user_id=target_pet.user_id,
                notification_type=NotificationType.NEW_MATCH,
                pet_id=body.target_pet_id,
                related_pet_id=body.pet_id,
                match_id=match_id,
                message=f"It's a match! {target_pet.name} and {swiper_pet.name} liked each other!",
            )
            db.add(notification_target)
    
    await db.commit()
    await db.refresh(swipe)
    
    return SwipeResponse(
        swiper_pet_id=swipe.swiper_pet_id,
        target_pet_id=swipe.target_pet_id,
        action=swipe.action.value,
        is_match=is_match,
        match_id=match_id,
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
    return {
        "pets": [PetPublicResponse.model_validate(p) for p in pets],
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


@router.get("/swipe-history")
async def get_swipe_history(
    pet_id: uuid.UUID = Query(description="Your pet ID"),
    action: str | None = Query(default=None, description="Filter by action: like or skip"),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the swipe history for your pet - see who you've liked or skipped.
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
    
    filters = [Swipe.swiper_pet_id == pet_id]
    if action:
        if action not in ["like", "skip"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action. Must be 'like' or 'skip'",
            )
        filters.append(Swipe.action == SwipeAction(action))
    
    swipes_result = await db.execute(
        select(Swipe)
        .where(*filters)
        .order_by(Swipe.created_at.desc())
        .limit(limit)
    )
    
    swipes = swipes_result.scalars().all()
    
    if not swipes:
        return {"swipes": [], "total": 0}
    
    # Get target pet details
    target_pet_ids = [s.target_pet_id for s in swipes]
    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_(target_pet_ids))
    )
    pets_map = {pet.id: pet for pet in pets_result.scalars().all()}
    
    result = []
    for swipe in swipes:
        target_pet = pets_map.get(swipe.target_pet_id)
        if target_pet:
            result.append({
                "swipe_id": str(swipe.id),
                "action": swipe.action.value,
                "created_at": swipe.created_at.isoformat(),
                "target_pet": PetPublicResponse.model_validate(target_pet),
            })
    
    return {"swipes": result, "total": len(result)}
