from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.whatsapp_inbound import handle_evolution_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/evolution")
async def evolution_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public, unauthenticated endpoint. Evolution does not sign webhook
    payloads, so we treat anything received here as advisory and only
    operate on subscribers that already match a phone number we've stored.
    No phone match -> no DB write."""
    payload = await request.json()
    return await handle_evolution_webhook(payload, db)
