"""Stripe subscription → User tier sync.

`sync_subscription(db, user, stripe_sub_obj)` maps the price ID of the
subscription's primary item to one of our tiers (starter / pro / business)
and writes back to `users`. We keep the Stripe IDs around so the customer
portal call can find the customer without round-tripping by email.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User


def _tier_from_price_id(price_id: str) -> str | None:
    s = get_settings()
    if price_id == s.stripe_price_starter and price_id:
        return "starter"
    if price_id == s.stripe_price_pro and price_id:
        return "pro"
    if price_id == s.stripe_price_business and price_id:
        return "business"
    return None


async def sync_subscription(db: AsyncSession, user: User, stripe_sub: Any) -> None:
    """Update `user` from a Stripe Subscription object (from API or webhook).
    Idempotent — safe to call repeatedly."""
    items = (stripe_sub.get("items") or {}).get("data") or []
    price_id = ""
    if items:
        price_id = (items[0].get("price") or {}).get("id") or ""
    tier = _tier_from_price_id(price_id)
    status = stripe_sub.get("status") or "unknown"
    user.stripe_subscription_id = stripe_sub.get("id") or user.stripe_subscription_id
    user.stripe_customer_id = stripe_sub.get("customer") or user.stripe_customer_id
    user.subscription_status = status
    if tier is not None and status in ("active", "trialing", "past_due"):
        user.tier = tier
    elif status in ("canceled", "unpaid", "incomplete_expired"):
        # Subscription ended; back to expired so quotas zero out.
        user.tier = "trial_expired"
    await db.commit()
