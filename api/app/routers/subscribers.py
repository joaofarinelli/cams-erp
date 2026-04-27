from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscriber, User
from app.db.session import get_db
from app.schemas.subscribers import SubscriberCreate, SubscriberOut
from app.security.cognito import get_current_user

router = APIRouter(prefix="/me/subscribers", tags=["me"])


@router.post("", response_model=SubscriberOut, status_code=201)
async def create_subscriber(
    payload: SubscriberCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Subscriber:
    sub = Subscriber(owner_id=user.id, kind=payload.kind, target=payload.target.strip())
    db.add(sub)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(Subscriber).where(
                Subscriber.owner_id == user.id,
                Subscriber.kind == payload.kind,
                Subscriber.target == payload.target.strip(),
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Subscriber conflict")
        return existing
    await db.refresh(sub)
    return sub


@router.get("", response_model=list[SubscriberOut])
async def list_subscribers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Subscriber]:
    result = await db.execute(
        select(Subscriber).where(Subscriber.owner_id == user.id).order_by(Subscriber.created_at)
    )
    return list(result.scalars().all())


@router.delete("/{subscriber_id}", status_code=204)
async def delete_subscriber(
    subscriber_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Subscriber).where(
            Subscriber.id == subscriber_id, Subscriber.owner_id == user.id
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscriber not found")
    await db.delete(sub)
    await db.commit()
