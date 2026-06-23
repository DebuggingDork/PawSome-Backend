from uuid import UUID

from pydantic import BaseModel


class UnmatchRequest(BaseModel):
    """Request to unmatch from a match, optionally blocking the other user.

    Requirements: 7.1, 7.2
    """

    block_user: bool = False


class UnmatchResponse(BaseModel):
    """Response after unmatching from a match.

    Requirements: 7.1, 7.2, 7.7, 11.9
    """

    message: str
    match_id: UUID
    blocked: bool
    notification_sent: bool
