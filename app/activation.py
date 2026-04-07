"""
Client-facing endpoints:
  POST /activate     – activate a license on a device
  POST /deactivate   – release a device slot
  POST /validate     – check if an activation is still valid
"""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Activation, AuditLog, _ensure_aware
from app.licenses import get_license_by_hash, activation_count
from app.security import hash_key, sign_certificate
from app.schemas import (
    ActivationRequest,
    ActivationResponse,
    DeactivationRequest,
    ValidateRequest,
    ValidateResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Client"])


# ── POST /activate ───────────────────────────────────────

@router.post("/activate", response_model=ActivationResponse)
def activate(
    body: ActivationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    key_hash = hash_key(body.license_key)
    lic = get_license_by_hash(db, key_hash)

    # 1. Key must exist
    if not lic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")

    # 2. License must be active
    if lic.status != "active":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"License is {lic.status}",
        )

    client_ip = request.client.host if request.client else None

    # 3. Same device reinstall → reissue certificate
    existing = (
        db.query(Activation)
        .filter(
            Activation.license_id == lic.id,
            Activation.device_id == body.device_id,
            Activation.revoked_at.is_(None),
        )
        .first()
    )
    if existing:
        existing.last_ip = client_ip
        cert = _build_certificate(lic, existing)
        _audit(db, lic.id, "reactivated", {
            "device_id": body.device_id,
            "ip": client_ip,
        })
        db.commit()
        return ActivationResponse(
            status="ok",
            message="Re-activated on same device",
            certificate=cert,
        )

    # 4. Different device → check limit
    active = activation_count(lic)
    if active >= lic.max_devices:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Device limit reached ({lic.max_devices}). "
            "Deactivate another device first.",
        )

    # 5. Create activation
    expires_at = datetime.now(timezone.utc) + timedelta(days=lic.expires_after_days)
    act = Activation(
        license_id=lic.id,
        device_id=body.device_id,
        app_id=body.app_id,
        expires_at=expires_at,
        last_ip=client_ip,
    )
    db.add(act)
    db.flush()

    cert = _build_certificate(lic, act)
    _audit(db, lic.id, "activated", {
        "device_id": body.device_id,
        "activation_id": act.id,
        "ip": client_ip,
    })
    db.commit()

    return ActivationResponse(
        status="ok",
        message="License activated successfully",
        certificate=cert,
    )


# ── POST /deactivate ────────────────────────────────────

@router.post("/deactivate", response_model=ActivationResponse)
def deactivate(
    body: DeactivationRequest,
    db: Session = Depends(get_db),
):
    key_hash = hash_key(body.license_key)
    lic = get_license_by_hash(db, key_hash)
    if not lic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")

    act = (
        db.query(Activation)
        .filter(
            Activation.license_id == lic.id,
            Activation.device_id == body.device_id,
            Activation.revoked_at.is_(None),
        )
        .first()
    )
    if not act:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active activation for this device")

    act.revoked_at = datetime.now(timezone.utc)
    _audit(db, lic.id, "deactivated", {"device_id": body.device_id})
    db.commit()

    return ActivationResponse(status="ok", message="Device deactivated")


# ── POST /validate ───────────────────────────────────────

@router.post("/validate", response_model=ValidateResponse)
def validate(
    body: ValidateRequest,
    db: Session = Depends(get_db),
):
    key_hash = hash_key(body.license_key)
    lic = get_license_by_hash(db, key_hash)

    if not lic or lic.status != "active":
        return ValidateResponse(valid=False, message="Invalid or revoked license")

    act = (
        db.query(Activation)
        .filter(
            Activation.license_id == lic.id,
            Activation.device_id == body.device_id,
            Activation.revoked_at.is_(None),
        )
        .first()
    )
    if not act:
        return ValidateResponse(valid=False, message="Not activated on this device")

    if act.expires_at and _ensure_aware(act.expires_at) < datetime.now(timezone.utc):
        return ValidateResponse(valid=False, message="Activation expired")

    _audit(db, lic.id, "validated", {"device_id": body.device_id})
    db.commit()

    return ValidateResponse(
        valid=True,
        message="License is valid",
        expires_at=act.expires_at,
    )


# ── Internal helpers ─────────────────────────────────────

def _build_certificate(lic, act: Activation) -> dict:
    """Create an Ed25519-signed offline certificate."""
    payload = {
        "license_id": lic.id,
        "app_id": act.app_id,
        "device_id": act.device_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": act.expires_at.isoformat() if act.expires_at else None,
    }
    return sign_certificate(payload)


def _audit(db: Session, license_id: str, event: str, meta: dict):
    db.add(AuditLog(
        license_id=license_id,
        event_type=event,
        metadata_json=json.dumps(meta, default=str),
    ))
