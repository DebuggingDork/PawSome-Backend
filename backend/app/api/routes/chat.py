import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.match import Match
from app.models.message import Message
from app.models.pet_profile import PetProfile
from app.models.user import User
from app.schemas.chat import ChatHistoryResponse, MessageResponse
from app.services.chat_manager import manager

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


async def verify_match_access(match_id: uuid.UUID, user: User, db: AsyncSession) -> tuple[Match, uuid.UUID]:
    """Verify user has access to this match and return the match + user's pet_id"""
    # Get the match
    result = await db.execute(
        select(Match).where(Match.id == match_id)
    )
    match = result.scalar_one_or_none()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Get user's pets in this match
    user_pets = await db.execute(
        select(PetProfile.id).where(
            PetProfile.user_id == user.id,
            PetProfile.id.in_([match.pet1_id, match.pet2_id]),
            PetProfile.is_active.is_(True),
        )
    )
    user_pet_ids = [row[0] for row in user_pets.all()]
    
    if not user_pet_ids:
        raise HTTPException(status_code=403, detail="You are not part of this match")
    
    return match, user_pet_ids[0]


@router.websocket("/ws/{match_id}")
async def websocket_chat(
    websocket: WebSocket,
    match_id: str,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time chat.
    Connect: ws://localhost:8000/chat/ws/{match_id}?token=your-jwt-token
    """
    from app.core.security import verify_token
    
    # Verify token
    try:
        user_id = verify_token(token, "access")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Get DB session
    async for db in get_db():
        try:
            # Get user
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Verify match access
            try:
                match_uuid = uuid.UUID(match_id)
                match, pet_id = await verify_match_access(match_uuid, user, db)
            except HTTPException:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Initialize Redis connection if needed
            redis = await get_redis()
            if not manager.redis_client:
                await manager.initialize(redis)
            
            # Connect the WebSocket
            await manager.connect(websocket, match_id, str(pet_id))
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    msg_type = message_data.get("type", "message")
                    
                    if msg_type == "message":
                        # Save message to database
                        content = message_data.get("content", "").strip()
                        if not content:
                            continue
                        
                        new_message = Message(
                            match_id=match_uuid,
                            sender_pet_id=pet_id,
                            content=content,
                            msg_type=message_data.get("msg_type", "text"),
                        )
                        db.add(new_message)
                        await db.commit()
                        await db.refresh(new_message)
                        
                        # Broadcast to all instances via Redis
                        broadcast_data = {
                            "type": "message",
                            "data": {
                                "id": str(new_message.id),
                                "match_id": str(new_message.match_id),
                                "sender_pet_id": str(new_message.sender_pet_id),
                                "content": new_message.content,
                                "msg_type": new_message.msg_type,
                                "created_at": new_message.created_at.isoformat(),
                            }
                        }
                        await manager.broadcast_message(match_id, broadcast_data)
                    
                    elif msg_type == "typing":
                        # Broadcast typing indicator (no DB save)
                        typing_data = {
                            "type": "typing",
                            "data": {
                                "pet_id": str(pet_id),
                                "is_typing": message_data.get("is_typing", True),
                            }
                        }
                        await manager.broadcast_message(match_id, typing_data)
                    
            except WebSocketDisconnect:
                manager.disconnect(match_id, str(pet_id))
            except Exception as e:
                manager.disconnect(match_id, str(pet_id))
                raise
        finally:
            await db.close()


@router.get("/{match_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    match_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: uuid.UUID | None = Query(default=None, description="Get messages before this message ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chat history for a match (paginated, newest first)"""
    
    # Verify access
    match, pet_id = await verify_match_access(match_id, user, db)
    
    # Build query
    filters = [
        Message.match_id == match_id,
        Message.is_deleted.is_(False),
    ]
    
    if before:
        # Get timestamp of 'before' message
        before_result = await db.execute(
            select(Message.created_at).where(Message.id == before)
        )
        before_time = before_result.scalar_one_or_none()
        if before_time:
            filters.append(Message.created_at < before_time)
    
    # Get messages
    result = await db.execute(
        select(Message)
        .where(*filters)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()
    
    # Get total count
    total_result = await db.execute(
        select(Message)
        .where(Message.match_id == match_id, Message.is_deleted.is_(False))
    )
    total = len(total_result.scalars().all())
    
    return ChatHistoryResponse(
        messages=[MessageResponse.model_validate(m) for m in reversed(messages)],
        total=total,
        has_more=len(messages) == limit,
    )


@router.get("/{match_id}/status")
async def get_chat_status(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chat status (online users, unread count, etc.)"""
    
    # Verify access
    match, user_pet_id = await verify_match_access(match_id, user, db)
    
    # Get the other pet in the match
    other_pet_id = match.pet2_id if match.pet1_id == user_pet_id else match.pet1_id
    
    # Check if other pet is online
    is_online = await manager.is_pet_online(str(other_pet_id))
    
    # Get unread count (messages sent by other pet after last read)
    # For now, just return total message count
    result = await db.execute(
        select(Message)
        .where(
            Message.match_id == match_id,
            Message.sender_pet_id == other_pet_id,
            Message.is_deleted.is_(False),
        )
    )
    messages = result.scalars().all()
    
    return {
        "match_id": str(match_id),
        "other_pet_id": str(other_pet_id),
        "is_online": is_online,
        "message_count": len(messages),
    }
