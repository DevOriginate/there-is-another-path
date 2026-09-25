from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from . import db
from .access import (
    active_purchase,
    consultation_summary,
    purchase_access,
    remove_access_cookie_entry,
    session_vault,
    switch_access_cookie,
)

router = APIRouter()


@router.get("/api/v1/access/me")
def access_status(request: Request):
    vault = session_vault(request)
    if not vault:
        raise HTTPException(403, "No private access session")

    purchases = db.get_purchases_by_ids(vault["purchase_ids"])
    by_id = {purchase["id"]: purchase for purchase in purchases}
    active_id = int(vault["active_purchase_id"])
    active_purchase = by_id.get(active_id)
    active_access = purchase_access(active_purchase)
    active_assessment = (
        db.get_assessment_for_purchase(active_id)
        if active_purchase and active_access["valid"]
        else None
    )

    return {
        "valid": active_access["valid"],
        "state": active_access["state"],
        "reason": active_access.get("reason"),
        "completed": bool(active_assessment),
        "report_url": "/report" if active_assessment and active_access["valid"] else None,
        "active_purchase_id": active_id,
        "expires_at": active_access.get("expires_at"),
        "days_remaining": active_access.get("days_remaining", 0),
        "can_purchase_new": True,
        "consultations": [
            consultation_summary(purchase, active_id)
            for purchase in purchases
        ],
    }


@router.post("/api/v1/access/switch/{purchase_id}")
def switch_access(request: Request, purchase_id: int):
    vault = session_vault(request)
    if not vault or purchase_id not in vault["purchase_ids"]:
        raise HTTPException(403, "That consultation is not in this private session")

    purchase = db.get_purchase_by_id(purchase_id)
    access = purchase_access(purchase)
    if not access["valid"]:
        raise HTTPException(410, "That consultation access has expired or is unavailable")

    assessment = db.get_assessment_for_purchase(purchase_id)
    response = JSONResponse(
        {
            "ok": True,
            "completed": bool(assessment),
            "destination": "/report" if assessment else "/start",
        }
    )
    switch_access_cookie(response, request, purchase_id)
    return response


@router.post("/api/v1/privacy/delete")
def delete_active_consultation_data(request: Request):
    purchase = active_purchase(request)
    db.delete_personal_data(purchase["id"])
    response = JSONResponse({"ok": True, "destination": "/"})
    remove_access_cookie_entry(response, request, purchase["id"])
    return response
