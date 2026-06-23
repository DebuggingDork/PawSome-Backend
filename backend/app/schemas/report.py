from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.report import ReportReason


class CreateReportRequest(BaseModel):
    reported_user_id: UUID
    reported_pet_id: UUID | None = None
    reason: ReportReason
    description: str = Field(min_length=10, max_length=2000)


class ReportResponse(BaseModel):
    id: UUID
    status: str = "pending_review"
    created_at: datetime

    model_config = {"from_attributes": True}
