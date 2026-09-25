from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response

from . import db
from .config import ASSESSMENT_RETENTION_DAYS, SESSION_COOKIE_NAME, SESSION_COOKIE_SECURE
from .security import (
    merge_private_session,
    read_private_session,
    remove_from_private_session,
    switch_private_session,
)

SESSION_MAX_AGE = ASSESSMENT_RETENTION_DAYS * 24 * 60 * 60


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def purchase_access(purchase: dict | None) -> dict[str, Any]:
    if not purchase:
        return {"state": "missing", "valid": False, "expires_at": None, "days_remaining": 0}

    status = str(purchase.get("status") or "pending")
    if status != "paid":
        return {"state": status, "valid": False, "expires_at": None, "days_remaining": 0}

    paid_at = parse_iso(purchase.get("paid_at")) or parse_iso(purchase.get("created_at"))
    expires_at = paid_at + timedelta(days=ASSESSMENT_RETENTION_DAYS) if paid_at else None

    if purchase.get("access_revoked_at"):
        return {
            "state": "revoked",
            "reason": purchase.get("access_revoked_reason") or "revoked",
            "valid": False,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "days_remaining": 0,
        }

    now = datetime.now(timezone.utc)
    if expires_at and now >= expires_at:
        return {
            "state": "expired",
            "valid": False,
            "expires_at": expires_at.isoformat(),
            "days_remaining": 0,
        }

    if expires_at:
        seconds = max(0, int((expires_at - now).total_seconds()))
        days_remaining = max(1, (seconds + 86399) // 86400)
    else:
        days_remaining = ASSESSMENT_RETENTION_DAYS

    return {
        "state": "active",
        "valid": True,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "days_remaining": days_remaining,
    }


def session_vault(request: Request) -> dict[str, Any] | None:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_value:
        return None
    try:
        return read_private_session(cookie_value, SESSION_MAX_AGE)
    except ValueError:
        return None


def set_cookie_value(response: Response, value: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=value,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def set_access_cookie(response: Response, request: Request, purchase_id: int) -> None:
    value = merge_private_session(
        request.cookies.get(SESSION_COOKIE_NAME),
        purchase_id,
        SESSION_MAX_AGE,
    )
    set_cookie_value(response, value)


def switch_access_cookie(response: Response, request: Request, purchase_id: int) -> None:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        raise HTTPException(403, "Private access session is required")
    try:
        value = switch_private_session(cookie, purchase_id, SESSION_MAX_AGE)
    except ValueError as exc:
        raise HTTPException(403, "That consultation is not in this private session") from exc
    set_cookie_value(response, value)


def remove_access_cookie_entry(response: Response, request: Request, purchase_id: int) -> None:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    remaining = None
    if cookie:
        try:
            remaining = remove_from_private_session(cookie, purchase_id, SESSION_MAX_AGE)
        except ValueError:
            remaining = None
    if remaining:
        set_cookie_value(response, remaining)
    else:
        clear_access_cookie(response)


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def active_purchase(request: Request) -> dict:
    vault = session_vault(request)
    if not vault:
        raise HTTPException(403, "Valid paid access is required")

    active_id = int(vault["active_purchase_id"])
    purchase = db.get_purchase_by_id(active_id)
    if purchase_access(purchase)["valid"]:
        return purchase

    for candidate in db.get_purchases_by_ids(vault["purchase_ids"]):
        if purchase_access(candidate)["valid"]:
            return candidate

    raise HTTPException(403, "Paid access is expired, revoked, refunded, or unavailable")


def consultation_summary(purchase: dict, active_purchase_id: int) -> dict[str, Any]:
    access = purchase_access(purchase)
    assessment = db.get_assessment_for_purchase(purchase["id"]) if access["valid"] else None
    return {
        "purchase_id": purchase["id"],
        "active": purchase["id"] == active_purchase_id,
        "state": access["state"],
        "valid": access["valid"],
        "completed": bool(assessment),
        "report_url": "/report" if assessment and access["valid"] else None,
        "purchased_at": purchase.get("paid_at") or purchase.get("created_at"),
        "expires_at": access.get("expires_at"),
        "days_remaining": access.get("days_remaining", 0),
    }
