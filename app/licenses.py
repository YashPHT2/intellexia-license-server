"""License business-logic layer (CRUD + audit logging)."""

import json
from typing import Optional
from sqlalchemy.orm import Session

from app.models import License, Activation, AuditLog
from app.schemas import LicenseCreateRequest
from app.security import generate_license_key, hash_key
from app.config import get_settings


# ── Create ───────────────────────────────────────────────

def create_license(db: Session, data: LicenseCreateRequest) -> tuple[License, str]:
    """
    Create a new license.
    Returns (license_obj, raw_key) – the raw key is shown once and never stored.
    """
    raw_key = generate_license_key()
    key_hash = hash_key(raw_key)

    lic = License(
        license_key_hash=key_hash,
        status="active",
        max_devices=data.max_devices,
        expires_after_days=data.expires_after_days,
        notes=data.notes,
    )
    db.add(lic)
    db.flush()  # get lic.id before audit log

    _audit(db, lic.id, "created", {"max_devices": data.max_devices})
    db.commit()
    db.refresh(lic)
    return lic, raw_key


# ── Read ─────────────────────────────────────────────────

def get_license_by_hash(db: Session, key_hash: str) -> Optional[License]:
    return (
        db.query(License)
        .filter(License.license_key_hash == key_hash)
        .first()
    )


def get_license_by_id(db: Session, license_id: str) -> Optional[License]:
    return db.query(License).filter(License.id == license_id).first()


def list_licenses(db: Session, skip: int = 0, limit: int = 100) -> list[License]:
    return db.query(License).order_by(License.created_at.desc()).offset(skip).limit(limit).all()


# ── Revoke ───────────────────────────────────────────────

def revoke_license(db: Session, lic: License) -> License:
    """Set status to revoked – existing activations remain for audit, but
    validation will reject them."""
    lic.status = "revoked"
    _audit(db, lic.id, "revoked", {})
    db.commit()
    db.refresh(lic)
    return lic


# ── Reissue ──────────────────────────────────────────────

def reissue_license(db: Session, lic: License) -> tuple[License, str]:
    """
    Generate a fresh key for the same license row.
    Old key hash becomes invalid; status is reset to active.
    """
    raw_key = generate_license_key()
    lic.license_key_hash = hash_key(raw_key)
    lic.status = "active"
    _audit(db, lic.id, "reissued", {})
    db.commit()
    db.refresh(lic)
    return lic, raw_key


# ── Helpers ──────────────────────────────────────────────

def activation_count(lic: License) -> int:
    """Count non-revoked activations."""
    return sum(1 for a in lic.activations if a.is_active)


def _audit(db: Session, license_id: str, event: str, meta: dict):
    db.add(AuditLog(
        license_id=license_id,
        event_type=event,
        metadata_json=json.dumps(meta, default=str),
    ))
