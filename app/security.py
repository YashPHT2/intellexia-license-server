"""
Security utilities:
  • License-key generation  (INTELX-XXXX-XXXX-XXXX)
  • SHA-256 hashing         (never store raw keys)
  • Ed25519 signing          (offline certificate verification)
  • Admin API-token guard
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives import serialization
from fastapi import Header, HTTPException, status

from app.config import get_settings


# ── License-key generation ───────────────────────────────

def generate_license_key() -> str:
    """
    Generate a human-readable key like INTELX-8K3Q-7H2P-91LM.
    Uses uppercase alphanumeric, no ambiguous chars (0/O, 1/I/L).
    """
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    segments = [
        "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(3)
    ]
    return f"INTELX-{'-'.join(segments)}"


# ── Hashing ──────────────────────────────────────────────

def hash_key(raw_key: str) -> str:
    """SHA-256 hash of a license key – this is what gets stored in the DB."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


# ── Ed25519 signing ──────────────────────────────────────

_private_key_cache: Ed25519PrivateKey | None = None


def _load_private_key() -> Ed25519PrivateKey:
    """Load the Ed25519 private key from settings (base64-encoded PEM)."""
    global _private_key_cache
    if _private_key_cache is not None:
        return _private_key_cache

    settings = get_settings()
    pem_b64 = settings.LICENSE_PRIVATE_KEY_PEM
    if not pem_b64:
        raise RuntimeError(
            "LICENSE_PRIVATE_KEY_PEM is not set. "
            "Generate one with: python -m app.security"
        )

    pem_bytes = base64.b64decode(pem_b64)
    _private_key_cache = serialization.load_pem_private_key(pem_bytes, password=None)  # type: ignore[assignment]
    return _private_key_cache


def get_public_key_pem() -> str:
    """Return the public key PEM (for embedding in the desktop app)."""
    pk = _load_private_key().public_key()
    return pk.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def sign_certificate(payload: dict) -> dict:
    """
    Create a signed offline certificate.

    Returns:
        {
          "payload": { ... },
          "signature": "base64url..."
        }
    """
    priv = _load_private_key()
    payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
    sig = priv.sign(payload_bytes)
    return {
        "payload": payload,
        "signature": base64.urlsafe_b64encode(sig).decode(),
    }


# ── Admin API-token guard ────────────────────────────────

def verify_admin_token(
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
):
    """FastAPI dependency – rejects requests without a valid admin token."""
    settings = get_settings()
    if not hmac.compare_digest(x_admin_token, settings.ADMIN_API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token",
        )
    return x_admin_token


# ── CLI: generate a fresh Ed25519 keypair ────────────────

if __name__ == "__main__":
    """
    Run:  python -m app.security
    Prints a base64-encoded private key PEM (for LICENSE_PRIVATE_KEY_PEM env var)
    and the raw public key PEM (for the desktop app).
    """
    private_key = Ed25519PrivateKey.generate()

    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_b64 = base64.b64encode(priv_pem).decode()

    print("=" * 60)
    print("LICENSE_PRIVATE_KEY_PEM  (set this as an env var on Render)")
    print("=" * 60)
    print(priv_b64)
    print()
    print("=" * 60)
    print("PUBLIC KEY PEM  (embed this in the desktop app)")
    print("=" * 60)
    print(pub_pem.decode())
