"""bcrypt password hashing — direct binding. Passlib's adapter is broken
against bcrypt 5.x (silently falls back to a 72-byte-limit shim that errors
on long passwords), so we call bcrypt directly."""

from __future__ import annotations

import bcrypt

ROUNDS = 12
_MAX_BCRYPT_BYTES = 72


def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:_MAX_BCRYPT_BYTES], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
