"""Field-level AES-256-GCM encryption for sensitive columns (Section 20-23).

Prototype key management: a single KEK loaded from env. Production would use envelope
encryption with a per-record DEK wrapped by a KMS-managed KEK; this is explicitly a
demo-grade simplification, not a production key-management design.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_key = base64.b64decode(settings.field_encryption_key_b64)
if len(_key) != 32:
    raise ValueError("FIELD_ENCRYPTION_KEY_B64 must decode to exactly 32 bytes (AES-256)")

_aesgcm = AESGCM(_key)


def encrypt_value(plaintext: str) -> bytes:
    nonce = os.urandom(12)
    ciphertext = _aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_value(blob: bytes) -> str:
    nonce, ciphertext = blob[:12], blob[12:]
    return _aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
