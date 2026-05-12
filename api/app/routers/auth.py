from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConsentLog, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.security.jwt_self import issue_token
from app.security.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)
    terms_accepted: bool = Field(default=False)
    policy_version: str = Field(default="v1.0")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class MeOut(BaseModel):
    id: str
    email: str
    name: str | None
    email_verified: bool
    created_at: datetime


def _user_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "name": u.name,
        "email_verified": u.email_verified_at is not None,
    }


@router.post("/signup", response_model=TokenOut, status_code=201)
async def signup(
    payload: SignupIn, request: Request, db: AsyncSession = Depends(get_db)
) -> TokenOut:
    if not payload.terms_accepted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Você deve aceitar os termos de uso e a política de privacidade",
        )
    email = payload.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email já cadastrado")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip() if payload.name else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    for doc_type in ("privacy", "terms"):
        log = ConsentLog(
            user_id=user.id,
            doc_type=doc_type,
            version=payload.policy_version,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(log)
    user.policy_version = payload.policy_version
    await db.commit()
    token = issue_token(user.id, user.email)
    return TokenOut(access_token=token, user=_user_dict(user))


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou senha incorretos")
    token = issue_token(user.id, user.email)
    return TokenOut(access_token=token, user=_user_dict(user))


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )
