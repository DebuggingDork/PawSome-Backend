"""
Reports endpoint — allows users to report other users (and optionally their pets)
for safety violations.

Requirements covered: 5.4, 5.5, 11.6, 12.2, 13.6, 13.7, 13.8, 15.3
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import report_rate_limit
from app.models.pet_profile import PetProfile
from app.models.report import Report
from app.models.user import User
from app.schemas.report import CreateReportRequest, ReportResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: CreateReportRequest,
    _rate_limit: None = Depends(report_rate_limit),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Submit a report against another user, optionally targeting a specific pet profile.

    - 400 if the reporter tries to report themselves.
    - 404 if the reported user does not exist.
    - 404 if a reported_pet_id is supplied but the pet does not exist or does not
      belong to the reported user.
    - 429 if the reporter exceeds 5 reports per day (enforced by report_rate_limit).
    """

    # 1. Self-report guard
    if body.reported_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot report yourself",
        )

    # 2. Verify reported user exists
    reported_user_result = await db.execute(
        select(User).where(User.id == body.reported_user_id)
    )
    reported_user = reported_user_result.scalar_one_or_none()
    if reported_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reported user not found",
        )

    # 3. Optional pet verification
    if body.reported_pet_id is not None:
        pet_result = await db.execute(
            select(PetProfile).where(PetProfile.id == body.reported_pet_id)
        )
        pet = pet_result.scalar_one_or_none()
        if pet is None or pet.user_id != body.reported_user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reported pet not found or does not belong to the reported user",
            )

    # 4. Sanitize description
    sanitized_description = body.description.strip()

    # 5. Persist the report
    report = Report(
        reporter_user_id=current_user.id,
        reported_user_id=body.reported_user_id,
        reported_pet_id=body.reported_pet_id,
        reason=body.reason,
        description=sanitized_description,
    )
    db.add(report)

    # 6. Flush to obtain report.id before logging
    await db.flush()

    # 7. Admin notification — structured log (Notification model requires pet FKs
    #    which admins may not have, so we use logging as the notification mechanism)
    logger.info(
        "New report submitted: report_id=%s, reporter=%s, reported_user=%s, reason=%s",
        report.id,
        current_user.id,
        body.reported_user_id,
        body.reason,
    )

    # 8. Commit
    await db.commit()
    await db.refresh(report)

    # 9. Return 201
    return ReportResponse(
        id=report.id,
        status="pending_review",
        created_at=report.created_at,
    )
