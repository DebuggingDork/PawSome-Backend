import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.match import Match
from app.models.notification import Notification, NotificationType
from app.models.pet_profile import PetProfile
from app.models.playdate import Playdate, PlaydateStatus
from app.models.user import User
from app.schemas.playdate import (
    PlaydateCreate,
    PlaydateListResponse,
    PlaydatePetInfo,
    PlaydateRespondRequest,
    PlaydateResponse,
)
from app.services.notification_manager import manager as notification_manager

router = APIRouter(prefix="/matches", tags=["playdates"])


async def _verify_match_membership(
    match_id: uuid.UUID, user: User, db: AsyncSession
) -> tuple[Match, uuid.UUID, uuid.UUID]:
    """404 if the match doesn't exist, 403 if the caller isn't part of it.
    Returns (match, your_pet_id, other_pet_id)."""
    result = await db.execute(
        select(Match).where(Match.id == match_id, Match.deleted_at.is_(None))
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    user_pets = await db.execute(
        select(PetProfile.id).where(
            PetProfile.user_id == user.id,
            PetProfile.id.in_([match.pet1_id, match.pet2_id]),
        )
    )
    user_pet_ids = {row[0] for row in user_pets.all()}
    if not user_pet_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not part of this match")

    your_pet_id = next(iter(user_pet_ids))
    other_pet_id = match.pet2_id if your_pet_id == match.pet1_id else match.pet1_id
    return match, your_pet_id, other_pet_id


async def _to_response(
    playdate: Playdate, pets_map: dict[uuid.UUID, PetProfile], viewer_pet_id: uuid.UUID
) -> PlaydateResponse:
    proposer = pets_map[playdate.proposed_by_pet_id]
    recipient = pets_map[playdate.proposed_to_pet_id]
    return PlaydateResponse(
        id=playdate.id,
        match_id=playdate.match_id,
        scheduled_at=playdate.scheduled_at,
        location_name=playdate.location_name,
        latitude=playdate.latitude,
        longitude=playdate.longitude,
        address=playdate.address,
        pincode=playdate.pincode,
        note=playdate.note,
        status=playdate.status.value,
        proposed_by_pet=PlaydatePetInfo.model_validate(proposer),
        proposed_to_pet=PlaydatePetInfo.model_validate(recipient),
        is_mine_to_respond=(
            playdate.status == PlaydateStatus.PENDING
            and playdate.proposed_to_pet_id == viewer_pet_id
        ),
        created_at=playdate.created_at,
        responded_at=playdate.responded_at,
    )


async def _push_playdate_notification(notification: Notification, other_pet: PetProfile) -> None:
    await notification_manager.broadcast_to_user(
        str(notification.user_id),
        {
            "type": "notification",
            "data": {
                "id": str(notification.id),
                "notification_type": notification.notification_type.value,
                "message": notification.message,
                "is_read": notification.is_read,
                "is_super": False,
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


@router.post("/{match_id}/playdates", response_model=PlaydateResponse, status_code=status.HTTP_201_CREATED)
async def propose_playdate(
    match_id: uuid.UUID,
    body: PlaydateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Propose a real-world meetup to the other owner in a match."""
    match, your_pet_id, other_pet_id = await _verify_match_membership(match_id, user, db)

    if body.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled_at must be in the future")

    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_([your_pet_id, other_pet_id]))
    )
    pets_map = {p.id: p for p in pets_result.scalars().all()}

    playdate = Playdate(
        match_id=match.id,
        proposed_by_pet_id=your_pet_id,
        proposed_to_pet_id=other_pet_id,
        scheduled_at=body.scheduled_at,
        location_name=body.location_name,
        latitude=body.latitude,
        longitude=body.longitude,
        address=body.address,
        pincode=body.pincode,
        note=body.note,
    )
    db.add(playdate)

    your_pet = pets_map[your_pet_id]
    other_pet = pets_map[other_pet_id]
    notification = Notification(
        user_id=other_pet.user_id,
        notification_type=NotificationType.PLAYDATE_PROPOSED,
        pet_id=other_pet_id,
        related_pet_id=your_pet_id,
        match_id=match.id,
        message=f"{your_pet.name} proposed a playdate at {body.location_name}!",
    )
    db.add(notification)

    await db.commit()
    await db.refresh(playdate)
    await db.refresh(notification)
    await _push_playdate_notification(notification, your_pet)

    return await _to_response(playdate, pets_map, your_pet_id)


@router.get("/{match_id}/playdates", response_model=PlaydateListResponse)
async def list_playdates(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List every playdate (any status) proposed within this match."""
    match, your_pet_id, other_pet_id = await _verify_match_membership(match_id, user, db)

    result = await db.execute(
        select(Playdate).where(Playdate.match_id == match.id).order_by(Playdate.scheduled_at.desc())
    )
    playdates = result.scalars().all()
    if not playdates:
        return PlaydateListResponse(items=[], total=0)

    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_([your_pet_id, other_pet_id]))
    )
    pets_map = {p.id: p for p in pets_result.scalars().all()}

    items = [await _to_response(p, pets_map, your_pet_id) for p in playdates]
    return PlaydateListResponse(items=items, total=len(items))


@router.post("/{match_id}/playdates/{playdate_id}/respond", response_model=PlaydateResponse)
async def respond_to_playdate(
    match_id: uuid.UUID,
    playdate_id: uuid.UUID,
    body: PlaydateRespondRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept or decline a pending playdate proposal (recipient only)."""
    match, your_pet_id, other_pet_id = await _verify_match_membership(match_id, user, db)

    result = await db.execute(
        select(Playdate).where(Playdate.id == playdate_id, Playdate.match_id == match.id)
    )
    playdate = result.scalar_one_or_none()
    if not playdate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playdate not found")

    if playdate.proposed_to_pet_id != your_pet_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the invited owner can respond")

    if playdate.status != PlaydateStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This playdate already has a response")

    playdate.status = PlaydateStatus.ACCEPTED if body.status == "accepted" else PlaydateStatus.DECLINED
    playdate.responded_at = datetime.now(timezone.utc)

    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_([your_pet_id, other_pet_id]))
    )
    pets_map = {p.id: p for p in pets_result.scalars().all()}
    your_pet = pets_map[your_pet_id]
    proposer_pet = pets_map[other_pet_id]

    verb = "accepted" if body.status == "accepted" else "declined"
    notification = Notification(
        user_id=proposer_pet.user_id,
        notification_type=NotificationType.PLAYDATE_RESPONSE,
        pet_id=other_pet_id,
        related_pet_id=your_pet_id,
        match_id=match.id,
        message=f"{your_pet.name}'s owner {verb} the playdate at {playdate.location_name}.",
    )
    db.add(notification)

    await db.commit()
    await db.refresh(playdate)
    await db.refresh(notification)
    await _push_playdate_notification(notification, your_pet)

    return await _to_response(playdate, pets_map, your_pet_id)


@router.post("/{match_id}/playdates/{playdate_id}/cancel", response_model=PlaydateResponse)
async def cancel_playdate(
    match_id: uuid.UUID,
    playdate_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a playdate you proposed (pending or already-accepted, while still upcoming)."""
    match, your_pet_id, other_pet_id = await _verify_match_membership(match_id, user, db)

    result = await db.execute(
        select(Playdate).where(Playdate.id == playdate_id, Playdate.match_id == match.id)
    )
    playdate = result.scalar_one_or_none()
    if not playdate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playdate not found")

    if playdate.proposed_by_pet_id != your_pet_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the proposer can cancel")

    if playdate.status not in (PlaydateStatus.PENDING, PlaydateStatus.ACCEPTED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This playdate can no longer be cancelled")

    playdate.status = PlaydateStatus.CANCELLED
    playdate.responded_at = datetime.now(timezone.utc)

    pets_result = await db.execute(
        select(PetProfile).where(PetProfile.id.in_([your_pet_id, other_pet_id]))
    )
    pets_map = {p.id: p for p in pets_result.scalars().all()}
    your_pet = pets_map[your_pet_id]
    other_pet = pets_map[other_pet_id]

    notification = Notification(
        user_id=other_pet.user_id,
        notification_type=NotificationType.PLAYDATE_RESPONSE,
        pet_id=other_pet_id,
        related_pet_id=your_pet_id,
        match_id=match.id,
        message=f"{your_pet.name}'s owner cancelled the playdate at {playdate.location_name}.",
    )
    db.add(notification)

    await db.commit()
    await db.refresh(playdate)
    await db.refresh(notification)
    await _push_playdate_notification(notification, your_pet)

    return await _to_response(playdate, pets_map, your_pet_id)


@router.get("/playdates/upcoming", response_model=PlaydateListResponse)
async def get_upcoming_playdates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every accepted, still-upcoming playdate across all of the caller's matches."""
    my_pets_result = await db.execute(select(PetProfile.id).where(PetProfile.user_id == user.id))
    my_pet_ids = [row[0] for row in my_pets_result.all()]
    if not my_pet_ids:
        return PlaydateListResponse(items=[], total=0)

    result = await db.execute(
        select(Playdate)
        .where(
            or_(
                Playdate.proposed_by_pet_id.in_(my_pet_ids),
                Playdate.proposed_to_pet_id.in_(my_pet_ids),
            ),
            Playdate.status == PlaydateStatus.ACCEPTED,
            Playdate.scheduled_at > datetime.now(timezone.utc),
        )
        .order_by(Playdate.scheduled_at.asc())
    )
    playdates = result.scalars().all()
    if not playdates:
        return PlaydateListResponse(items=[], total=0)

    pet_ids = set(my_pet_ids)
    for p in playdates:
        pet_ids.add(p.proposed_by_pet_id)
        pet_ids.add(p.proposed_to_pet_id)
    pets_result = await db.execute(select(PetProfile).where(PetProfile.id.in_(pet_ids)))
    pets_map = {p.id: p for p in pets_result.scalars().all()}

    items = []
    for p in playdates:
        viewer_pet_id = p.proposed_by_pet_id if p.proposed_by_pet_id in my_pet_ids else p.proposed_to_pet_id
        items.append(await _to_response(p, pets_map, viewer_pet_id))

    return PlaydateListResponse(items=items, total=len(items))
