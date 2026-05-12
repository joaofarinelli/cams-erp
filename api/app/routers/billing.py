"""Stripe checkout + customer portal + webhook endpoints.

Flow:
  1. Web calls POST /billing/checkout {price: tier} -> redirects to Stripe.
  2. Customer pays; Stripe sends customer.subscription.created webhook.
  3. We verify signature, sync user.tier via stripe_sync.sync_subscription.
  4. Web calls /billing/portal for cancel/update -> Stripe Customer Portal.

Idempotency: every webhook event_id is logged in stripe_events_processed;
second delivery is a no-op.

Without STRIPE_API_KEY set, the endpoints respond 503 — keeps dev/test
deployments from accidentally hitting prod Stripe.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import StripeEventProcessed, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.services.stripe_sync import sync_subscription


log = logging.getLogger("billing")
router = APIRouter(prefix="/billing", tags=["billing"])

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _ensure_stripe() -> str:
    s = get_settings()
    if not s.stripe_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "billing not configured"
        )
    stripe.api_key = s.stripe_api_key
    return s.stripe_api_key


def _price_for_tier(tier: str) -> str | None:
    s = get_settings()
    return {
        "starter": s.stripe_price_starter,
        "pro": s.stripe_price_pro,
        "business": s.stripe_price_business,
    }.get(tier) or None


class CheckoutIn(BaseModel):
    tier: str  # "starter" | "pro" | "business"


class CheckoutOut(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutOut)
async def create_checkout(
    payload: CheckoutIn,
    user: User = Depends(get_current_user),
) -> CheckoutOut:
    _ensure_stripe()
    price = _price_for_tier(payload.tier)
    if not price:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown tier '{payload.tier}'")
    s = get_settings()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=user.stripe_customer_id or None,
        customer_email=user.email if not user.stripe_customer_id else None,
        line_items=[{"price": price, "quantity": 1}],
        success_url=s.billing_success_url,
        cancel_url=s.billing_cancel_url,
        metadata={"user_id": str(user.id)},
    )
    return CheckoutOut(url=session.url)


class PortalOut(BaseModel):
    url: str


@router.post("/portal", response_model=PortalOut)
async def billing_portal(
    user: User = Depends(get_current_user),
) -> PortalOut:
    _ensure_stripe()
    if not user.stripe_customer_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "no Stripe customer for this account yet"
        )
    s = get_settings()
    sess = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=s.billing_success_url,
    )
    return PortalOut(url=sess.url)


@webhooks_router.post("/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = get_settings()
    if not s.stripe_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook not configured")
    body = await request.body()
    try:
        event = stripe.Webhook.construct_event(body, stripe_signature, s.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad signature")

    event_id = event.get("id") or ""
    event_type = event.get("type") or ""

    # Idempotency: second delivery of the same event is a no-op.
    existing = (
        await db.execute(
            select(StripeEventProcessed).where(StripeEventProcessed.event_id == event_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"ok": True, "duplicate": True}

    data: dict[str, Any] = (event.get("data") or {}).get("object") or {}
    customer_id = data.get("customer") if isinstance(data.get("customer"), str) else None
    if customer_id:
        user = (
            await db.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
        ).scalar_one_or_none()
        if user is None and event_type.startswith("customer.subscription"):
            # First subscription event for a brand new customer — match by
            # session metadata if present, else by email lookup.
            user_id_meta = (data.get("metadata") or {}).get("user_id")
            if user_id_meta:
                user = (
                    await db.execute(select(User).where(User.id == user_id_meta))
                ).scalar_one_or_none()
        if user is not None and event_type.startswith("customer.subscription"):
            await sync_subscription(db, user, data)

    db.add(StripeEventProcessed(event_id=event_id, type=event_type))
    await db.commit()
    log.info("stripe webhook handled: %s", event_type)
    return {"ok": True}
