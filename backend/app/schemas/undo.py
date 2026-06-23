from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class UndoSwipeRequest(BaseModel):
    """Request to undo a previous swipe"""
    swipe_id: UUID


class UndoSwipeResponse(BaseModel):
    """Response after undoing a swipe"""
    message: str
    swipe_id: UUID
    action_taken: Literal["swipe_reverted", "match_deleted"]
