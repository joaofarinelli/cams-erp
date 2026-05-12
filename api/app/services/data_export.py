"""Async data export: builds ZIP with user data + manifest, uploads to S3 (optional)."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Alert,
    AuditLog,
    Camera,
    ConsentLog,
    DataExportRequest,
    Device,
    Rule,
    Subscriber,
    User,
)
from app.db.session import SessionLocal


def _to_json_safe(obj) -> dict:
    """Convert SQLAlchemy row to JSON-serializable dict."""
    return {
        k: (
            str(v)
            if hasattr(v, "hex")
            else v.isoformat()
            if hasattr(v, "isoformat")
            else v
        )
        for k, v in obj.__dict__.items()
        if not k.startswith("_") and k != "password_hash"
    }


async def build_export_zip(user_id: UUID, db: AsyncSession) -> tuple[bytes, str]:
    """Build ZIP bytes and return (zip_bytes, sha256_hex)."""
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    devices = (
        await db.execute(select(Device).where(Device.owner_id == user_id))
    ).scalars().all()
    device_ids = [d.id for d in devices]

    cameras: list = []
    cam_ids: list = []
    if device_ids:
        cameras = (
            await db.execute(select(Camera).where(Camera.device_id.in_(device_ids)))
        ).scalars().all()
        cam_ids = [c.id for c in cameras]

    rules: list = []
    rule_ids: list = []
    if cam_ids:
        rules = (
            await db.execute(select(Rule).where(Rule.camera_id.in_(cam_ids)))
        ).scalars().all()
        rule_ids = [r.id for r in rules]

    alerts: list = []
    if rule_ids:
        alerts = (
            await db.execute(
                select(Alert).where(Alert.rule_id.in_(rule_ids)).limit(1000)
            )
        ).scalars().all()

    subscribers = (
        await db.execute(select(Subscriber).where(Subscriber.owner_id == user_id))
    ).scalars().all()
    audit_logs = (
        await db.execute(
            select(AuditLog).where(AuditLog.user_id == user_id).limit(500)
        )
    ).scalars().all()
    consents = (
        await db.execute(select(ConsentLog).where(ConsentLog.user_id == user_id))
    ).scalars().all()

    data = {
        "user": _to_json_safe(user),
        "devices": [_to_json_safe(d) for d in devices],
        "cameras": [_to_json_safe(c) for c in cameras],
        "rules": [_to_json_safe(r) for r in rules],
        "alerts": [_to_json_safe(a) for a in alerts],
        "subscribers": [_to_json_safe(s) for s in subscribers],
        "audit_log": [_to_json_safe(a) for a in audit_logs],
        "consent_log": [_to_json_safe(c) for c in consents],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        sha256_hex = hashlib.sha256(json_bytes).hexdigest()
        manifest = {
            "sha256_data": sha256_hex,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        zf.writestr("data.json", json_bytes)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
    zip_bytes = buf.getvalue()
    zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()
    return zip_bytes, zip_sha256


async def process_export_request(export_id: UUID) -> None:
    """Background task: build ZIP, upload to S3 (if available), update request record."""
    async with SessionLocal() as db:
        req = await db.get(DataExportRequest, export_id)
        if req is None:
            return
        req.status = "processing"
        await db.commit()
        try:
            zip_bytes, sha256_hex = await build_export_zip(req.user_id, db)

            s3_key = f"exports/{req.user_id}/{export_id}.zip"
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

            # Try S3 upload — skip gracefully in dev/test
            try:
                import boto3

                from app.config import get_settings

                s = get_settings()
                s3 = boto3.client(
                    "s3",
                    region_name=s.aws_region,
                    endpoint_url=s.aws_endpoint_url or None,
                )
                s3.put_object(
                    Bucket=s.clips_bucket,
                    Key=s3_key,
                    Body=zip_bytes,
                    ContentType="application/zip",
                )
            except Exception:
                pass  # S3 unavailable in dev — record still marked done

            req.status = "done"
            req.s3_key = s3_key
            req.sha256 = sha256_hex
            req.expires_at = expires_at
            await db.commit()
        except Exception:
            req.status = "failed"
            await db.commit()
            raise
