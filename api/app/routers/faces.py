"""Face enrollment endpoints.

The web panel uploads 3-5 photos per person; we forward each photo (as
base64 JPEG) to one of the user's online agents via the existing
`face_extract` control-WS job, collect any embeddings returned, and
persist a `face_enrollments` row. When no agent has insightface bundled,
embeddings come back empty and the row is still stored — matching turns
on automatically once a release bundles the model. No DB rewrite needed.
"""

from __future__ import annotations

import base64
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, FaceEnrollment, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.services.agent_control import AgentOfflineError, registry


router = APIRouter(prefix="/faces", tags=["faces"])


class FaceEnrollIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    photos: list[str] = Field(min_length=1, max_length=10)  # data URLs OR raw b64


class FaceEnrollmentOut(BaseModel):
    id: UUID
    name: str
    embedding_count: int
    photo_count: int
    created_at: str


_DATA_URL_RE = re.compile(r"^data:image/[^;]+;base64,")


def _strip_data_url(s: str) -> str:
    return _DATA_URL_RE.sub("", s, count=1)


async def _first_online_device(user_id: UUID, db: AsyncSession) -> Device | None:
    """Pick any of the user's devices that has an active control WS to
    proxy face_extract jobs. None if all offline."""
    rows = (
        await db.execute(select(Device).where(Device.owner_id == user_id))
    ).scalars().all()
    for d in rows:
        if registry.is_online(str(d.id)):
            return d
    return None


@router.post("", response_model=FaceEnrollmentOut, status_code=201)
async def enroll_face(
    payload: FaceEnrollIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FaceEnrollmentOut:
    device = await _first_online_device(user.id, db)
    embeddings: list[list[float]] = []
    if device is not None:
        for raw in payload.photos:
            b64 = _strip_data_url(raw)
            try:
                resp = await registry.call(
                    str(device.id),
                    "face_extract",
                    {"jpeg_b64": b64},
                    timeout=15.0,
                )
            except AgentOfflineError:
                break
            if not resp.get("ok"):
                continue
            for emb in resp.get("result", {}).get("embeddings") or []:
                embeddings.append(emb)

    enrollment = FaceEnrollment(
        owner_id=user.id,
        name=payload.name,
        embeddings=embeddings,
        photo_s3_keys=None,  # storage TBD when insightface ships
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return FaceEnrollmentOut(
        id=enrollment.id,
        name=enrollment.name,
        embedding_count=len(embeddings),
        photo_count=len(payload.photos),
        created_at=enrollment.created_at.isoformat(),
    )


@router.get("", response_model=list[FaceEnrollmentOut])
async def list_face_enrollments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FaceEnrollmentOut]:
    rows = (
        await db.execute(
            select(FaceEnrollment)
            .where(FaceEnrollment.owner_id == user.id)
            .order_by(FaceEnrollment.created_at.desc())
        )
    ).scalars().all()
    return [
        FaceEnrollmentOut(
            id=r.id,
            name=r.name,
            embedding_count=len(r.embeddings or []),
            photo_count=len(r.photo_s3_keys or []),
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.delete("/{enrollment_id}", status_code=204)
async def delete_face_enrollment(
    enrollment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(FaceEnrollment).where(
            FaceEnrollment.id == enrollment_id, FaceEnrollment.owner_id == user.id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await db.delete(row)
    await db.commit()
