from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.services.digest import run_digest_for_owner

router = APIRouter(prefix="/digest", tags=["me"])


@router.post("/run-now", status_code=200)
async def run_now(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send the daily digest for the current owner immediately. Useful for
    smoke testing the digest pipeline without waiting for the scheduled hour."""
    if not get_settings().digest_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "digest disabled")
    sent = await run_digest_for_owner(db, user)
    return {"sent": sent}
