"""
Admin endpoints (protected by X-Admin-Token header):
  POST   /admin/licenses               – generate a new license key
  GET    /admin/licenses               – list all licenses
  GET    /admin/licenses/{id}          – single license detail
  POST   /admin/licenses/{id}/revoke   – revoke a license
  POST   /admin/licenses/{id}/reissue  – generate a new key for same license
  GET    /admin/licenses/{id}/activations
  GET    /admin/licenses/{id}/audit
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import verify_admin_token
from app.models import Activation, AuditLog
from app.schemas import (
    LicenseCreateRequest,
    LicenseCreateResponse,
    LicenseOut,
    ActivationOut,
    AuditLogOut,
)
from app.licenses import (
    create_license,
    get_license_by_id,
    list_licenses,
    revoke_license,
    reissue_license,
    activation_count,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_token)],
)


# ── POST /admin/licenses ────────────────────────────────

@router.post("/licenses", response_model=LicenseCreateResponse, status_code=201)
def admin_create_license(
    body: LicenseCreateRequest,
    db: Session = Depends(get_db),
):
    """Generate a new license key. The raw key is returned ONCE."""
    lic, raw_key = create_license(db, body)
    return LicenseCreateResponse(
        id=lic.id,
        license_key=raw_key,
        status=lic.status,
        max_devices=lic.max_devices,
        expires_after_days=lic.expires_after_days,
        created_at=lic.created_at,
    )


# ── GET /admin/licenses ─────────────────────────────────

@router.get("/licenses", response_model=list[LicenseOut])
def admin_list_licenses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    licenses = list_licenses(db, skip=skip, limit=limit)
    return [
        LicenseOut(
            id=lic.id,
            license_key_hash=lic.license_key_hash,
            status=lic.status,
            max_devices=lic.max_devices,
            expires_after_days=lic.expires_after_days,
            created_at=lic.created_at,
            notes=lic.notes,
            activation_count=activation_count(lic),
        )
        for lic in licenses
    ]


# ── GET /admin/licenses/{id} ────────────────────────────

@router.get("/licenses/{license_id}", response_model=LicenseOut)
def admin_get_license(license_id: str, db: Session = Depends(get_db)):
    lic = _get_or_404(db, license_id)
    return LicenseOut(
        id=lic.id,
        license_key_hash=lic.license_key_hash,
        status=lic.status,
        max_devices=lic.max_devices,
        expires_after_days=lic.expires_after_days,
        created_at=lic.created_at,
        notes=lic.notes,
        activation_count=activation_count(lic),
    )


# ── POST /admin/licenses/{id}/revoke ────────────────────

@router.post("/licenses/{license_id}/revoke", response_model=LicenseOut)
def admin_revoke_license(license_id: str, db: Session = Depends(get_db)):
    lic = _get_or_404(db, license_id)
    lic = revoke_license(db, lic)
    return LicenseOut(
        id=lic.id,
        license_key_hash=lic.license_key_hash,
        status=lic.status,
        max_devices=lic.max_devices,
        expires_after_days=lic.expires_after_days,
        created_at=lic.created_at,
        notes=lic.notes,
        activation_count=activation_count(lic),
    )


# ── POST /admin/licenses/{id}/reissue ───────────────────

@router.post("/licenses/{license_id}/reissue", response_model=LicenseCreateResponse)
def admin_reissue_license(license_id: str, db: Session = Depends(get_db)):
    """Invalidate the old key and generate a fresh one."""
    lic = _get_or_404(db, license_id)
    lic, raw_key = reissue_license(db, lic)
    return LicenseCreateResponse(
        id=lic.id,
        license_key=raw_key,
        status=lic.status,
        max_devices=lic.max_devices,
        expires_after_days=lic.expires_after_days,
        created_at=lic.created_at,
    )


# ── GET /admin/licenses/{id}/activations ─────────────────

@router.get("/licenses/{license_id}/activations", response_model=list[ActivationOut])
def admin_list_activations(license_id: str, db: Session = Depends(get_db)):
    _get_or_404(db, license_id)
    return (
        db.query(Activation)
        .filter(Activation.license_id == license_id)
        .order_by(Activation.activated_at.desc())
        .all()
    )


# ── GET /admin/licenses/{id}/audit ───────────────────────

@router.get("/licenses/{license_id}/audit", response_model=list[AuditLogOut])
def admin_audit_log(license_id: str, db: Session = Depends(get_db)):
    _get_or_404(db, license_id)
    return (
        db.query(AuditLog)
        .filter(AuditLog.license_id == license_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )


# ── Helper ───────────────────────────────────────────────

def _get_or_404(db: Session, license_id: str):
    lic = get_license_by_id(db, license_id)
    if not lic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return lic
