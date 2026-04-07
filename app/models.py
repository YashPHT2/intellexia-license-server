"""
SQLAlchemy ORM models.

Three core tables:
  licenses    – one row per generated key (stores HASH only, never raw key)
  activations – one row per device activation
  audit_logs  – immutable event log for every license operation
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text,
)
from sqlalchemy.orm import relationship
from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    """Make a datetime timezone-aware (SQLite returns naive datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _new_id() -> str:
    return str(uuid.uuid4())


# ── Licenses ─────────────────────────────────────────────

class License(Base):
    __tablename__ = "licenses"

    id              = Column(String, primary_key=True, default=_new_id)
    license_key_hash = Column(String, unique=True, nullable=False, index=True)
    status          = Column(String, nullable=False, default="active")  # active | revoked | expired
    max_devices     = Column(Integer, nullable=False, default=1)
    created_at      = Column(DateTime(timezone=True), default=_utcnow)
    expires_after_days = Column(Integer, nullable=False, default=365)
    notes           = Column(Text, nullable=True)

    activations = relationship(
        "Activation", back_populates="license", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="license", cascade="all, delete-orphan"
    )


# ── Activations ──────────────────────────────────────────

class Activation(Base):
    __tablename__ = "activations"

    id           = Column(String, primary_key=True, default=_new_id)
    license_id   = Column(String, ForeignKey("licenses.id"), nullable=False, index=True)
    device_id    = Column(String, nullable=False, index=True)
    app_id       = Column(String, nullable=False, default="translateai-desktop")
    activated_at = Column(DateTime(timezone=True), default=_utcnow)
    expires_at   = Column(DateTime(timezone=True), nullable=True)
    revoked_at   = Column(DateTime(timezone=True), nullable=True)
    last_ip      = Column(String, nullable=True)

    license = relationship("License", back_populates="activations")

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at and _ensure_aware(self.expires_at) < _utcnow():
            return False
        return True


# ── Audit Logs ───────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id            = Column(String, primary_key=True, default=_new_id)
    license_id    = Column(String, ForeignKey("licenses.id"), nullable=True, index=True)
    event_type    = Column(String, nullable=False)  # created | activated | revoked | reissued | validated
    metadata_json = Column(Text, nullable=True)       # arbitrary JSON blob
    created_at    = Column(DateTime(timezone=True), default=_utcnow)

    license = relationship("License", back_populates="audit_logs")
