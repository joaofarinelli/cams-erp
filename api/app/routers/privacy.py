"""LGPD basics: export-me, soft-delete-me, and restore-me. The hard work (consent flow,
retention enforcement on clips on disk / S3, processor contract) lives
elsewhere; these endpoints satisfy the data-subject-rights minimum."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, AuditLog, Camera, ConsentLog, DataExportRequest, Device, Rule, Subscriber, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.security.jwt_self import verify_token as verify_self_token
from app.services.data_export import process_export_request

router = APIRouter(prefix="/me", tags=["me"])

GRACE_PERIOD_DAYS = 30


@router.get("/export", status_code=202)
async def request_data_export(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rate-limited async export. Queues ZIP build; client polls or waits for email."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = (
        await db.execute(
            select(DataExportRequest)
            .where(
                and_(
                    DataExportRequest.user_id == user.id,
                    DataExportRequest.requested_at >= one_hour_ago,
                )
            )
            .order_by(DataExportRequest.requested_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if recent is not None:
        retry_after = recent.requested_at + timedelta(hours=1)
        raise HTTPException(
            status_code=429,
            detail=f"Export já solicitado. Tente novamente após {retry_after.isoformat()}",
        )

    req = DataExportRequest(user_id=user.id)
    db.add(req)
    await db.commit()
    await db.refresh(req)

    background_tasks.add_task(process_export_request, req.id)

    return {
        "export_id": str(req.id),
        "status": "processing",
        "message": "Você receberá um link por email em instantes.",
    }


class AcceptTermsIn(BaseModel):
    policy_version: str = Field(default="v1.0")


@router.post("/accept-terms", status_code=200)
async def accept_terms(
    payload: AcceptTermsIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    for doc_type in ("privacy", "terms"):
        log = ConsentLog(
            user_id=user.id,
            doc_type=doc_type,
            version=payload.policy_version,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(log)
    user.policy_version = payload.policy_version
    await db.commit()
    return {"accepted": True, "version": payload.policy_version}


class DeleteMeRequest(BaseModel):
    reason: str | None = None


@router.delete("", status_code=status.HTTP_202_ACCEPTED)
async def delete_my_account(
    payload: DeleteMeRequest = DeleteMeRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete: sets deleted_at. Hard purge runs after 30-day grace period."""
    fresh = await db.get(User, user.id)
    if fresh is None:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.now(timezone.utc)
    fresh.deleted_at = now
    fresh.deletion_reason = payload.reason
    await db.commit()
    purge_at = now + timedelta(days=GRACE_PERIOD_DAYS)
    return {
        "deleted_at": now.isoformat(),
        "purge_at": purge_at.isoformat(),
        "message": "Sua conta será permanentemente excluída em 30 dias. Use POST /me/restore para cancelar.",
    }


@router.post("/restore", status_code=200)
async def restore_account(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> dict:
    """Restore a soft-deleted account within the 30-day grace period.

    Does NOT use get_current_user because that dependency blocks deleted accounts (410).
    Manually verifies the self-issued JWT and fetches the user without the deletion check.
    """
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]

    try:
        from uuid import UUID
        claims = verify_self_token(token)
        user_id = UUID(claims["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.deleted_at is None:
        return {"restored": False, "message": "Account is not deleted"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=GRACE_PERIOD_DAYS)
    if user.deleted_at < cutoff:
        raise HTTPException(status_code=410, detail="Account permanently deleted")

    user.deleted_at = None
    user.deletion_reason = None
    await db.commit()
    return {"restored": True}
