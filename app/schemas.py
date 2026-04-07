"""Pydantic v2 schemas for request / response validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Activation (client-facing)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ActivationRequest(BaseModel):
    license_key: str
    device_id: str
    app_id: str = "translateai-desktop"
    app_version: str = "1.0.0"


class OfflineCertificate(BaseModel):
    """Signed offline certificate returned to the desktop app."""
    payload: dict
    signature: str


class ActivationResponse(BaseModel):
    status: str                          # "ok" | "error"
    message: str
    certificate: Optional[OfflineCertificate] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Validation (client-facing)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ValidateRequest(BaseModel):
    license_key: str
    device_id: str


class ValidateResponse(BaseModel):
    valid: bool
    message: str
    expires_at: Optional[datetime] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Deactivation (client-facing)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DeactivationRequest(BaseModel):
    license_key: str
    device_id: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Admin – License management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LicenseCreateRequest(BaseModel):
    max_devices: int = 1
    expires_after_days: int = 365
    notes: Optional[str] = None


class LicenseCreateResponse(BaseModel):
    """Returned ONCE at creation – the only time the raw key is visible."""
    id: str
    license_key: str             # raw key, shown only this once
    status: str
    max_devices: int
    expires_after_days: int
    created_at: datetime


class LicenseOut(BaseModel):
    """Safe representation – never exposes the raw key."""
    id: str
    license_key_hash: str
    status: str
    max_devices: int
    expires_after_days: int
    created_at: datetime
    notes: Optional[str]
    activation_count: int = 0

    model_config = {"from_attributes": True}


class ActivationOut(BaseModel):
    id: str
    device_id: str
    app_id: str
    activated_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    last_ip: Optional[str]

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: str
    license_id: Optional[str]
    event_type: str
    metadata_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
