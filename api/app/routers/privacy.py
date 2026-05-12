"""LGPD basics: export-me, soft-delete-me, and restore-me. The hard work (consent flow,
retention enforcement on clips on disk / S3, processor contract) lives
elsewhere; these endpoints satisfy the data-subject-rights minimum."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, AuditLog, Camera, ConsentLog, Device, Rule, Subscriber, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.security.jwt_self import verify_token as verify_self_token

router = APIRouter(prefix="/me", tags=["me"])

GRACE_PERIOD_DAYS = 30


@router.get("/export")
async def export_my_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns every row this user owns. JSON; client renders/downloads."""
    devices = (
        await db.execute(select(Device).where(Device.owner_id == user.id))
    ).scalars().all()
    device_ids = [d.id for d in devices]
    cameras = (
        await db.execute(select(Camera).where(Camera.device_id.in_(device_ids))) if device_ids else None
    )
    cams = list(cameras.scalars().all()) if cameras is not None else []
    cam_ids = [c.id for c in cams]
    rules = (
        await db.execute(select(Rule).where(Rule.camera_id.in_(cam_ids))) if cam_ids else None
    )
    rs = list(rules.scalars().all()) if rules is not None else []
    rule_ids = [r.id for r in rs]
    alerts = (
        await db.execute(select(Alert).where(Alert.rule_id.in_(rule_ids))) if rule_ids else None
    )
    al = list(alerts.scalars().all()) if alerts is not None else []
    subs = (
        await db.execute(select(Subscriber).where(Subscriber.owner_id == user.id))
    ).scalars().all()
    audit_logs = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    consents = (
        await db.execute(
            select(ConsentLog)
            .where(ConsentLog.user_id == user.id)
            .order_by(ConsentLog.accepted_at.desc())
        )
    ).scalars().all()

    def _flat(obj):
        return {
            k: (str(v) if hasattr(v, "hex") else v.isoformat() if hasattr(v, "isoformat") else v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_") and k != "password_hash"
        }

    return {
        "user": _flat(user),
        "devices": [_flat(d) for d in devices],
        "cameras": [_flat(c) for c in cams],
        "rules": [_flat(r) for r in rs],
        "alerts": [_flat(a) for a in al],
        "subscribers": [_flat(s) for s in subs],
        "audit_log": [_flat(a) for a in audit_logs],
        "consent_log": [_flat(c) for c in consents],
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
