from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    """Client sends this to create a message"""
    match_id: UUID
    content: str = Field(min_length=1, max_length=5000)
    msg_type: str = Field(default="text", max_length=20)


class MessageResponse(BaseModel):
    """Message returned to clients"""
    id: UUID
    match_id: UUID
    sender_pet_id: UUID
    content: str
    msg_type: str
    created_at: datetime
    is_read: bool = False  # Calculated field
    
    model_config = {
        "from_attributes": True,
    }


class ChatHistoryResponse(BaseModel):
    """Paginated chat history"""
    messages: list[MessageResponse]
    total: int
    has_more: bool
    unread_count: int = 0


class WSMessage(BaseModel):
    """WebSocket message envelope"""
    type: str  # "message", "typing", "read", "error"
    data: dict


class MarkReadRequest(BaseModel):
    """Mark messages as read up to a specific message"""
    message_id: UUID


class ReadReceiptResponse(BaseModel):
    """Read receipt info for a match"""
    match_id: UUID
    your_last_read: UUID | None
    other_last_read: UUID | None
    unread_count: int
