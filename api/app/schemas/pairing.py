from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PairCodeOut(BaseModel):
    pair_code: str
    expires_at: datetime
    device_id: UUID


class PairVerifyIn(BaseModel):
    pair_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PairVerifyOut(BaseModel):
    device_id: UUID
    device_token: str  # raw, returned only here
