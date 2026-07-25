import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models.event import Event, EventRSVP
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.event import (
    AttendeeInfo,
    AttendeePetInfo,
    EventAttendeesResponse,
    EventCreate,
    EventCreatorInfo,
    EventListResponse,
    EventResponse,
    EventRSVPRequest,
    EventRSVPResponse,
    EventUpdate,
)

router = APIRouter(prefix="/events", tags=["events"])


async def _attendee_count(db: AsyncSession, event_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(EventRSVP).where(EventRSVP.event_id == event_id)
    )
    return result.scalar_one()


async def _to_response(
    event: Event, creator: User, db: AsyncSession, viewer: User | None
) -> EventResponse:
    count = await _attendee_count(db, event.id)

    your_status: str | None = None
    if viewer is not None:
        rsvp_result = await db.execute(
            select(EventRSVP.status).where(
                EventRSVP.event_id == event.id, EventRSVP.user_id == viewer.id
            )
        )
        row = rsvp_result.first()
        your_status = row[0] if row else None

    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        location_name=event.location_name,
        latitude=event.latitude,
        longitude=event.longitude,
        address=event.address,
        pincode=event.pincode,
        event_time=event.event_time,
        species=event.species,
        creator=EventCreatorInfo.model_validate(creator),
        attendee_count=count,
        is_cancelled=event.cancelled_at is not None,
        your_rsvp_status=your_status,
        created_at=event.created_at,
    )


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Post a local meetup for other owners to discover and RSVP to."""
    if body.event_time <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_time must be in the future")

    event = Event(
        creator_user_id=user.id,
        title=body.title,
        description=body.description,
        location_name=body.location_name,
        latitude=body.latitude,
        longitude=body.longitude,
        address=body.address,
        pincode=body.pincode,
        event_time=body.event_time,
        species=body.species.value if body.species else None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return await _to_response(event, user, db, user)


@router.get("", response_model=EventListResponse)
async def list_events(
    species: str | None = Query(default=None),
    upcoming_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Browse community events, soonest first."""
    filters = [Event.cancelled_at.is_(None)]
    if species:
        filters.append(Event.species == species)
    if upcoming_only:
        filters.append(Event.event_time > datetime.now(timezone.utc))

    total_result = await db.execute(select(func.count()).select_from(Event).where(*filters))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Event).where(*filters).order_by(Event.event_time.asc()).limit(limit).offset(offset)
    )
    events = result.scalars().all()

    if not events:
        return EventListResponse(items=[], total=total, limit=limit, offset=offset)

    creator_ids = {e.creator_user_id for e in events}
    creators_result = await db.execute(select(User).where(User.id.in_(creator_ids)))
    creators_map = {c.id: c for c in creators_result.scalars().all()}

    items = [await _to_response(e, creators_map[e.creator_user_id], db, user) for e in events]
    return EventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    creator_result = await db.execute(select(User).where(User.id == event.creator_user_id))
    creator = creator_result.scalar_one_or_none()
    if not creator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event creator not found")

    return await _to_response(event, creator, db, user)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.creator_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the organizer can edit this event")

    updates = body.model_dump(exclude_unset=True)
    if "event_time" in updates and updates["event_time"] is not None and updates["event_time"] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_time must be in the future")
    if "species" in updates and updates["species"] is not None:
        updates["species"] = updates["species"].value if hasattr(updates["species"], "value") else updates["species"]

    for field, value in updates.items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)

    return await _to_response(event, user, db, user)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-cancel an event you organized."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.creator_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the organizer can cancel this event")

    event.cancelled_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/{event_id}/rsvp", response_model=EventRSVPResponse)
async def rsvp_to_event(
    event_id: uuid.UUID,
    body: EventRSVPRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert the caller's RSVP for an event."""
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event or event.cancelled_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if body.pet_id is not None:
        pet_result = await db.execute(
            select(PetProfile).where(PetProfile.id == body.pet_id, PetProfile.user_id == user.id)
        )
        if pet_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this pet")

    existing_result = await db.execute(
        select(EventRSVP).where(EventRSVP.event_id == event_id, EventRSVP.user_id == user.id)
    )
    rsvp = existing_result.scalar_one_or_none()

    if rsvp:
        rsvp.status = body.status
        rsvp.pet_id = body.pet_id
    else:
        rsvp = EventRSVP(event_id=event_id, user_id=user.id, pet_id=body.pet_id, status=body.status)
        db.add(rsvp)

    await db.commit()
    await db.refresh(rsvp)

    return EventRSVPResponse(
        id=rsvp.id, event_id=rsvp.event_id, status=rsvp.status, pet_id=rsvp.pet_id, created_at=rsvp.created_at
    )


@router.delete("/{event_id}/rsvp", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_rsvp(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EventRSVP).where(EventRSVP.event_id == event_id, EventRSVP.user_id == user.id)
    )
    rsvp = result.scalar_one_or_none()
    if not rsvp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You haven't RSVP'd to this event")

    await db.delete(rsvp)
    await db.commit()


@router.get("/{event_id}/attendees", response_model=EventAttendeesResponse)
async def get_attendees(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    if event_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    rsvps_result = await db.execute(
        select(EventRSVP).where(EventRSVP.event_id == event_id).order_by(EventRSVP.created_at.asc())
    )
    rsvps = rsvps_result.scalars().all()
    if not rsvps:
        return EventAttendeesResponse(items=[], total=0)

    user_ids = {r.user_id for r in rsvps}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    pet_ids = {r.pet_id for r in rsvps if r.pet_id is not None}
    pets_map: dict[uuid.UUID, PetProfile] = {}
    if pet_ids:
        pets_result = await db.execute(select(PetProfile).where(PetProfile.id.in_(pet_ids)))
        pets_map = {p.id: p for p in pets_result.scalars().all()}

    items = []
    for r in rsvps:
        attendee = users_map.get(r.user_id)
        if not attendee:
            continue
        pet = pets_map.get(r.pet_id) if r.pet_id else None
        items.append(
            AttendeeInfo(
                user_id=attendee.id,
                full_name=attendee.full_name,
                profile_photo_url=attendee.profile_photo_url,
                status=r.status,
                pet=(
                    AttendeePetInfo(
                        id=pet.id, name=pet.name, species=pet.species.value, primary_photo_url=pet.primary_photo_url
                    )
                    if pet
                    else None
                ),
            )
        )

    return EventAttendeesResponse(items=items, total=len(items))
