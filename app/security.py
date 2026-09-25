from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_ENCRYPTION_KEY


PREFIX = "fernet:"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if not DATA_ENCRYPTION_KEY:
        raise RuntimeError("DATA_ENCRYPTION_KEY is required to protect assessment data")
    try:
        return Fernet(DATA_ENCRYPTION_KEY.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError("DATA_ENCRYPTION_KEY is not a valid Fernet key") from exc


def validate_data_encryption_key() -> None:
    _fernet()


def encrypt_json(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return PREFIX + _fernet().encrypt(raw).decode("utf-8")


def decrypt_json(value: str) -> Any:
    if value.startswith(PREFIX):
        token = value[len(PREFIX):].encode("utf-8")
        try:
            raw = _fernet().decrypt(token)
        except InvalidToken as exc:
            raise RuntimeError("Stored assessment data could not be decrypted") from exc
        return json.loads(raw.decode("utf-8"))
    # Backward compatibility for records created before Privacy V1.
    return json.loads(value)


def create_private_session(purchase_id: int) -> str:
    payload = json.dumps({"purchase_id": int(purchase_id)}, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def read_private_session(cookie_value: str, max_age_seconds: int) -> int:
    try:
        raw = _fernet().decrypt(cookie_value.encode("utf-8"), ttl=max_age_seconds)
        payload = json.loads(raw.decode("utf-8"))
        purchase_id = int(payload["purchase_id"])
        if purchase_id <= 0:
            raise ValueError("invalid purchase id")
        return purchase_id
    except (InvalidToken, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired private session") from exc
