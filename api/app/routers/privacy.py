"""LGPD basics: export-me and delete-me. The hard work (consent flow,
retention enforcement on clips on disk / S3, processor contract) lives
elsewhere; these endpoints satisfy the data-subject-rights minimum."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, AuditLog, Camera, Device, Rule, Subscriber, User
from app.db.session import get_db
from app.security.cognito import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


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
    }


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cascade-delete the user. ondelete=CASCADE on devices/subscribers takes
    care of children. Clip files on disk are not removed here — that's a
    background job concern (CAMS_RETENTION_DAYS_CLIPS)."""
    fresh = await db.get(User, user.id)
    if fresh is not None:
        await db.delete(fresh)
        await db.commit()
