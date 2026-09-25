from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import db
from .access import active_purchase, purchase_access, set_access_cookie
from .security import parse_recovery_reference, recovery_code, recovery_reference, verify_recovery_code

router = APIRouter()


@router.get("/api/v1/access/backup")
def access_backup(request: Request):
    purchase = active_purchase(request)
    access = purchase_access(purchase)
    return {
        "reference": recovery_reference(purchase["id"]),
        "key": recovery_code(purchase["id"]),
        "expires_at": access.get("expires_at"),
    }


class RestorePayload(BaseModel):
    reference: str = Field(min_length=4, max_length=32)
    key: str = Field(min_length=10, max_length=64)


@router.post("/api/v1/access/restore")
def restore_access(request: Request, payload: RestorePayload):
    try:
        purchase_id = parse_recovery_reference(payload.reference)
    except (TypeError, ValueError) as exc:
        raise HTTPException(403, "Invalid access backup") from exc

    purchase = db.get_purchase_by_id(purchase_id)
    if not purchase or not verify_recovery_code(purchase_id, payload.key):
        raise HTTPException(403, "Invalid access backup")

    access = purchase_access(purchase)
    if not access["valid"]:
        raise HTTPException(410, "This consultation is no longer active")

    assessment = db.get_assessment_for_purchase(purchase_id)
    response = JSONResponse({
        "ok": True,
        "destination": "/report" if assessment else "/start",
    })
    set_access_cookie(response, request, purchase_id)
    return response
