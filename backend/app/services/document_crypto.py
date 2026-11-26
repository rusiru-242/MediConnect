"""Application-level encryption at rest for uploaded documents (Phase 05, B8).

Algorithm: AES-256-GCM (authenticated encryption) from the ``cryptography`` package; no custom cryptography.

Stored file format (binary)::

    b"MCENC1" | key-id length (1 byte) | key id (ASCII) | 12-byte random nonce | ciphertext + 16-byte GCM tag

The associated data is ``"<store>/<relative path>"``, so a ciphertext copied to another patient's path or to another
store fails authentication. Plaintext only ever exists in memory: uploads are encrypted before the first write and
downloads are decrypted into the HTTP response, so no decrypted temporary file is created.

Keys come from ``DOCUMENT_ENCRYPTION_KEYS`` (never from source code): comma-separated ``keyId:base64(32 bytes)``,
newest first. New files use the first key; any listed key decrypts, which allows rotation (add a new first key,
re-encrypt with ``scripts/encrypt_existing_documents.py --rotate``, then remove the old key).

This is application-level encryption of files the backend manages. It is separate from (and does not replace) disk
or volume encryption on the server, MongoDB encryption at rest, and encrypted backups.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAGIC = b"MCENC1"
NONCE_BYTES = 12
KEY_BYTES = 32


class DocumentEncryptionError(Exception):
    """Raised for a missing key, a malformed container or a failed integrity check (message has no secrets)."""


@dataclass(frozen=True)
class Keyring:
    keys: Dict[str, bytes]
    current: Optional[str]

    @property
    def configured(self) -> bool:
        return self.current is not None


def parse_keyring(raw: Optional[str]) -> Keyring:
    keys: Dict[str, bytes] = {}
    order: List[str] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise DocumentEncryptionError("DOCUMENT_ENCRYPTION_KEYS entries must look like keyId:base64key.")
        kid, b64 = item.split(":", 1)
        kid = kid.strip()
        if not kid or len(kid) > 40 or not kid.replace("-", "").replace("_", "").isalnum():
            raise DocumentEncryptionError("Invalid document encryption key id.")
        try:
            key = base64.b64decode(b64.strip(), validate=True)
        except (binascii.Error, ValueError):
            raise DocumentEncryptionError(f"Document encryption key '{kid}' is not valid base64.") from None
        if len(key) != KEY_BYTES:
            raise DocumentEncryptionError(f"Document encryption key '{kid}' must be exactly 32 bytes.")
        if kid in keys:
            raise DocumentEncryptionError(f"Duplicate document encryption key id '{kid}'.")
        keys[kid] = key
        order.append(kid)
    return Keyring(keys=keys, current=order[0] if order else None)


def keyring() -> Keyring:
    from app.config.settings import settings
    return parse_keyring(os.environ.get("DOCUMENT_ENCRYPTION_KEYS") or settings.DOCUMENT_ENCRYPTION_KEYS)


def generate_key_entry(key_id: str) -> str:
    """A new ``keyId:base64key`` entry (for operators; printed only by the script that generates it)."""
    return f"{key_id}:{base64.b64encode(os.urandom(KEY_BYTES)).decode('ascii')}"


def is_encrypted(blob: bytes) -> bool:
    return blob.startswith(MAGIC)


def _aad(context: str) -> bytes:
    return context.replace("\\", "/").encode("utf-8")


def encrypt(plaintext: bytes, context: str, ring: Optional[Keyring] = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    ring = ring or keyring()
    if not ring.configured:
        raise DocumentEncryptionError("Document encryption is not configured.")
    kid = ring.current
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(ring.keys[kid]).encrypt(nonce, plaintext, _aad(context))
    return MAGIC + bytes([len(kid)]) + kid.encode("ascii") + nonce + sealed


def key_id_of(blob: bytes) -> Optional[str]:
    if not is_encrypted(blob) or len(blob) < len(MAGIC) + 1:
        return None
    n = blob[len(MAGIC)]
    return blob[len(MAGIC) + 1:len(MAGIC) + 1 + n].decode("ascii", "replace")


def decrypt(blob: bytes, context: str, ring: Optional[Keyring] = None) -> bytes:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not is_encrypted(blob):
        raise DocumentEncryptionError("Not an encrypted document.")
    ring = ring or keyring()
    kid = key_id_of(blob)
    start = len(MAGIC) + 1 + len(kid or "")
    nonce, sealed = blob[start:start + NONCE_BYTES], blob[start + NONCE_BYTES:]
    if not kid or kid not in ring.keys:
        raise DocumentEncryptionError("The key for this document is not available.")
    if len(nonce) != NONCE_BYTES or len(sealed) < 16:
        raise DocumentEncryptionError("Encrypted document is truncated.")
    try:
        return AESGCM(ring.keys[kid]).decrypt(nonce, sealed, _aad(context))
    except InvalidTag:
        raise DocumentEncryptionError("Encrypted document failed its integrity check.") from None


def seal_for_storage(plaintext: bytes, context: str) -> Tuple[bytes, Dict[str, object]]:
    """Bytes to write plus metadata to store. Without configured keys the file is stored as before and the
    metadata says so; production refuses to start without keys (runtime_safety)."""
    ring = keyring()
    if not ring.configured:
        logger.warning("Document stored without application-level encryption (no DOCUMENT_ENCRYPTION_KEYS).")
        return plaintext, {"encrypted": False}
    return encrypt(plaintext, context, ring), {"encrypted": True, "encryption": "AES-256-GCM",
                                               "encryptionKeyId": ring.current}


def open_from_storage(blob: bytes, context: str) -> bytes:
    """Plaintext of a stored file: decrypts encrypted files, returns legacy (pre-Phase-05) plaintext files as is."""
    return decrypt(blob, context) if is_encrypted(blob) else blob
