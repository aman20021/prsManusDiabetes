from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    role: Mapped[Role] = relationship("Role")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    preprocessing_version: Mapped[str] = mapped_column(String(32), nullable=False)
    offline_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromotionEvent(Base):
    __tablename__ = "promotion_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    from_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    upload_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship("User")


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id"), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preprocessing_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scaler_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_type: Mapped[str] = mapped_column(String(16), nullable=False)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prediction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    probability_positive: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
