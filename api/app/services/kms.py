"""Encrypt/decrypt RTSP credentials at rest.

Dev/test path: base64 only (deterministic, easy to debug).
Production path: AES-256-GCM with key from CAMS_KMS_KEY (base64-encoded 32B).
The first byte after b64 decode is reserved for a version tag.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


_NONCE_BYTES = 12


def _key() -> bytes | None:
    settings = get_settings()
    if settings.env in ("test", "dev"):
        return None
    raw = os.environ.get("CAMS_KMS_KEY", "")
    if not raw:
        raise RuntimeError("CAMS_KMS_KEY not set in production")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("CAMS_KMS_KEY must decode to 32 bytes")
    return key


def encrypt(plaintext: str) -> str:
    key = _key()
    if key is None:
        return base64.b64encode(plaintext.encode()).decode()
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(b"\x01" + nonce + ct).decode()


def decrypt(ciphertext_b64: str) -> str:
    key = _key()
    if key is None:
        return base64.b64decode(ciphertext_b64).decode()
    blob = base64.b64decode(ciphertext_b64)
    if not blob or blob[0] != 0x01:
        # Legacy base64 (pre-AESGCM rows). Fall back so old data still reads.
        return base64.b64decode(ciphertext_b64).decode()
    nonce = blob[1 : 1 + _NONCE_BYTES]
    ct = blob[1 + _NONCE_BYTES :]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
