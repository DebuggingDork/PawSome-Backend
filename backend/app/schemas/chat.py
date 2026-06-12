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
    
    model_config = {
        "from_attributes": True,
    }


class ChatHistoryResponse(BaseModel):
    """Paginated chat history"""
    messages: list[MessageResponse]
    total: int
    has_more: bool


class WSMessage(BaseModel):
    """WebSocket message envelope"""
    type: str  # "message", "typing", "read", "error"
    data: dict
