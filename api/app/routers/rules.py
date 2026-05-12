from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Rule, User
from app.db.session import get_db
from app.schemas.rules import RuleCreate, RuleOut, RuleUpdate
from app.security.cognito import get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])


async def _owned_rule(rule_id: UUID, user: User, db: AsyncSession) -> Rule:
    result = await db.execute(
        select(Rule).join(Camera).join(Device).where(Rule.id == rule_id, Device.owner_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    return rule


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Rule:
    result = await db.execute(
        select(Camera).join(Device).where(Camera.id == payload.camera_id, Device.owner_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    from app.services.quotas import tier_allows_intensity

    if not tier_allows_intensity(user.tier, payload.analysis_intensity):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"intensity '{payload.analysis_intensity}' not allowed on tier '{user.tier}'",
        )
    rule = Rule(
        camera_id=payload.camera_id,
        name=payload.name,
        enabled=payload.enabled,
        zones=payload.zones,
        sensitivity=payload.sensitivity,
        cooldown_seconds=payload.cooldown_seconds,
        custom_prompt=payload.custom_prompt,
        schedule=payload.schedule,
        analysis_intensity=payload.analysis_intensity,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("", response_model=list[RuleOut])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Rule]:
    result = await db.execute(
        select(Rule).join(Camera).join(Device).where(Device.owner_id == user.id)
    )
    return list(result.scalars().all())


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Rule:
    rule = await _owned_rule(rule_id, user, db)
    if payload.analysis_intensity is not None:
        from app.services.quotas import tier_allows_intensity

        if not tier_allows_intensity(user.tier, payload.analysis_intensity):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"intensity '{payload.analysis_intensity}' not allowed on tier '{user.tier}'",
            )
    for field in ("name", "enabled", "zones", "sensitivity", "cooldown_seconds", "custom_prompt", "schedule", "analysis_intensity"):
        v = getattr(payload, field)
        if v is not None:
            setattr(rule, field, v)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await _owned_rule(rule_id, user, db)
    await db.delete(rule)
    await db.commit()
