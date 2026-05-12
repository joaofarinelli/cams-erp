from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlertStatus(StrEnum):
    pending = "pending"
    seen = "seen"
    false_positive = "false_positive"


class SubscriberKind(StrEnum):
    whatsapp = "whatsapp"
    expo_push = "expo_push"


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    cognito_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tier: Mapped[str] = mapped_column(
        String(16), default="trial", server_default=sa.text("'trial'")
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(16), nullable=True)


class UsageMonthly(Base):
    __tablename__ = "usage_monthly"
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    month: Mapped[datetime] = mapped_column(Date, primary_key=True)  # type: ignore[name-defined]
    events_count: Mapped[int] = mapped_column(default=0, server_default=sa.text("0"))
    vlm_calls: Mapped[int] = mapped_column(default=0, server_default=sa.text("0"))
    vlm_cascade_calls: Mapped[int] = mapped_column(default=0, server_default=sa.text("0"))
    vlm_tokens_in: Mapped[int] = mapped_column(BigInteger, default=0, server_default=sa.text("0"))
    vlm_tokens_out: Mapped[int] = mapped_column(BigInteger, default=0, server_default=sa.text("0"))
    alerts_count: Mapped[int] = mapped_column(default=0, server_default=sa.text("0"))
    storage_gb_hours: Mapped[float] = mapped_column(default=0.0, server_default=sa.text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StripeEventProcessed(Base):
    __tablename__ = "stripe_events_processed"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pair_code: Mapped[str | None] = mapped_column(String(6), unique=True, nullable=True)
    pair_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    device_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    name: Mapped[str] = mapped_column(
        String(120), default="My PDV", server_default=sa.text("'My PDV'")
    )
    edge_yolo_enabled: Mapped[bool] = mapped_column(
        default=False, server_default=sa.false()
    )
    last_self_test_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentError(Base):
    __tablename__ = "agent_errors"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    kind: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(1024))
    traceback: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    rtsp_url_encrypted: Mapped[str] = mapped_column(String(1024))
    online: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    camera_id: Mapped[UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    enabled: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    zones: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=sa.text("'{}'::jsonb"))
    sensitivity: Mapped[int] = mapped_column(default=50, server_default=sa.text("50"))
    cooldown_seconds: Mapped[int] = mapped_column(default=300, server_default=sa.text("300"))
    custom_prompt: Mapped[str] = mapped_column(String(4000))
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analysis_intensity: Mapped[str] = mapped_column(
        String(16), default="normal", server_default=sa.text("'normal'")
    )
    rule_type: Mapped[str] = mapped_column(
        String(32), default="vlm", server_default=sa.text("'vlm'")
    )
    plate_whitelist: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    plate_blacklist: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    audio_classes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    camera_id: Mapped[UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"), index=True
    )
    s3_key: Mapped[str] = mapped_column(String(512))
    motion_score: Mapped[float] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column()
    processed: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    detected_plates: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    audio_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FaceEnrollment(Base):
    __tablename__ = "face_enrollments"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    embeddings: Mapped[list] = mapped_column(JSONB)
    photo_s3_keys: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Subscriber(Base):
    __tablename__ = "subscribers"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[SubscriberKind] = mapped_column(Enum(SubscriberKind, name="subscriber_kind"))
    target: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        sa.UniqueConstraint("owner_id", "kind", "target", name="uq_subscriber_owner_target"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="RESTRICT"), index=True)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), default=AlertStatus.pending
    )
    score: Mapped[float] = mapped_column()
    message: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(16))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsentLog(Base):
    __tablename__ = "consent_log"
    id: Mapped[UUID] = mapped_column(
        PGUUID, primary_key=True, default=uuid4, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    policy_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )
    doc_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(16))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[UUID] = mapped_column(
        PGUUID,
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
