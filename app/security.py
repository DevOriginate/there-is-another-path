from __future__ import annotations

import base64
import hashlib
import hmac
import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_ENCRYPTION_KEY


PREFIX = "fernet:"
MAX_SESSION_PURCHASES = 8


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


def _normalize_purchase_ids(values: Any) -> list[int]:
    ids: list[int] = []
    for value in values or []:
        try:
            purchase_id = int(value)
        except (TypeError, ValueError):
            continue
        if purchase_id > 0 and purchase_id not in ids:
            ids.append(purchase_id)
    return ids[-MAX_SESSION_PURCHASES:]


def create_private_session(
    purchase_ids: int | list[int],
    active_purchase_id: int | None = None,
) -> str:
    if isinstance(purchase_ids, int):
        ids = [purchase_ids]
    else:
        ids = _normalize_purchase_ids(purchase_ids)
    if not ids:
        raise ValueError("At least one purchase is required")

    active = int(active_purchase_id or ids[-1])
    if active not in ids:
        ids.append(active)
        ids = _normalize_purchase_ids(ids)

    payload = json.dumps(
        {
            "v": 2,
            "purchase_ids": ids,
            "active_purchase_id": active,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def read_private_session(cookie_value: str, max_age_seconds: int) -> dict[str, Any]:
    try:
        raw = _fernet().decrypt(cookie_value.encode("utf-8"), ttl=max_age_seconds)
        payload = json.loads(raw.decode("utf-8"))

        # Backward compatibility with Privacy V1 single-purchase cookies.
        if "purchase_id" in payload:
            purchase_id = int(payload["purchase_id"])
            if purchase_id <= 0:
                raise ValueError("invalid purchase id")
            return {
                "purchase_ids": [purchase_id],
                "active_purchase_id": purchase_id,
            }

        ids = _normalize_purchase_ids(payload.get("purchase_ids"))
        active = int(payload.get("active_purchase_id"))
        if not ids or active not in ids:
            raise ValueError("invalid session vault")
        return {
            "purchase_ids": ids,
            "active_purchase_id": active,
        }
    except (InvalidToken, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired private session") from exc


def merge_private_session(
    cookie_value: str | None,
    purchase_id: int,
    max_age_seconds: int,
) -> str:
    ids: list[int] = []
    if cookie_value:
        try:
            existing = read_private_session(cookie_value, max_age_seconds)
            ids = existing["purchase_ids"]
        except ValueError:
            ids = []
    ids.append(int(purchase_id))
    return create_private_session(_normalize_purchase_ids(ids), int(purchase_id))


def switch_private_session(
    cookie_value: str,
    purchase_id: int,
    max_age_seconds: int,
) -> str:
    existing = read_private_session(cookie_value, max_age_seconds)
    purchase_id = int(purchase_id)
    if purchase_id not in existing["purchase_ids"]:
        raise ValueError("Purchase is not in this private session")
    return create_private_session(existing["purchase_ids"], purchase_id)


def remove_from_private_session(
    cookie_value: str,
    purchase_id: int,
    max_age_seconds: int,
) -> str | None:
    existing = read_private_session(cookie_value, max_age_seconds)
    ids = [pid for pid in existing["purchase_ids"] if pid != int(purchase_id)]
    if not ids:
        return None
    active = existing["active_purchase_id"]
    if active == int(purchase_id) or active not in ids:
        active = ids[-1]
    return create_private_session(ids, active)


def _recovery_secret() -> bytes:
    # The persistent Fernet key is already a protected application secret.
    return base64.urlsafe_b64decode(DATA_ENCRYPTION_KEY.encode("utf-8"))


def recovery_reference(purchase_id: int) -> str:
    return f"PF-{int(purchase_id):08d}"


def parse_recovery_reference(reference: str) -> int:
    value = str(reference or "").strip().upper()
    if not value.startswith("PF-"):
        raise ValueError("Invalid recovery reference")
    purchase_id = int(value[3:])
    if purchase_id <= 0:
        raise ValueError("Invalid recovery reference")
    return purchase_id


def recovery_code(purchase_id: int) -> str:
    digest = hmac.new(
        _recovery_secret(),
        f"pathfinder-recovery:{int(purchase_id)}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    raw = base64.b32encode(digest[:16]).decode("ascii").rstrip("=")
    return "-".join(raw[i:i+5] for i in range(0, 25, 5))


def verify_recovery_code(purchase_id: int, supplied: str) -> bool:
    normalized = str(supplied or "").strip().upper().replace(" ", "")
    return hmac.compare_digest(normalized, recovery_code(purchase_id))
