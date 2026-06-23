from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateBlockRequest(BaseModel):
    blocked_user_id: UUID
    reason: str | None = None


class BlockedUserInfo(BaseModel):
    id: UUID
    full_name: str | None
    profile_photo_url: str | None

    model_config = {"from_attributes": True}


class BlockResponse(BaseModel):
    id: UUID
    blocking_user_id: UUID
    blocked_user_id: UUID
    created_at: datetime
    matches_affected: int

    model_config = {"from_attributes": True}


class BlockListItemResponse(BaseModel):
    id: UUID
    blocked_user: BlockedUserInfo
    created_at: datetime


class BlockListResponse(BaseModel):
    blocks: list[BlockListItemResponse]
    total: int
