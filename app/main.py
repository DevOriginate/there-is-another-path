from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .models import AssessmentInput, AssessmentResult, validate_free_text
from .engine import evaluate, load_paths
from . import db
from .payments import create_checkout, verify_success, handle_webhook
from .reporting import build_report
from .consultation import CONSULTATION_VERSION, compose_unique_consultation, consultation_fragment_hashes
from .security import validate_data_encryption_key
from .access import active_purchase, purchase_access, set_access_cookie, remove_access_cookie_entry
from .access_routes import router as access_router
from .draft_routes import router as draft_router
from .config import (
    PRODUCT_PRICE_USD,
    DEMO_MODE,
    META_PIXEL_ID,
    ADMIN_TOKEN,
    SUPPORT_EMAIL,
    REFUND_DAYS,
    BILLING_LABEL,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
    ASSESSMENT_RETENTION_DAYS,
    EXPOSE_API_DOCS,
)

APP_DIR = Path(__file__).resolve().parent
STATIC = APP_DIR / "static"
SESSION_MAX_AGE = ASSESSMENT_RETENTION_DAYS * 24 * 60 * 60


def _set_access_cookie(response, request: Request, purchase_id: int) -> None:
    set_access_cookie(response, request, purchase_id)


def _clear_access_cookie(response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def _paid_purchase_from_request(request: Request) -> dict:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_value:
        raise HTTPException(403, "Valid paid access is required")
    try:
        purchase_id = read_private_session(cookie_value, SESSION_MAX_AGE)
    except ValueError as exc:
        raise HTTPException(403, "Valid paid access is required") from exc
    purchase = db.get_purchase_by_id(purchase_id)
    if not purchase or not purchase_access(purchase)["valid"]:
        raise HTTPException(403, "Valid paid access is required")
    return purchase


# Prelaunch entitlement resolver. This later definition intentionally supersedes
# the legacy single-purchase resolver above while old cookies remain compatible.
def _paid_purchase_from_request(request: Request) -> dict:
    return active_purchase(request)


async def _privacy_maintenance_loop():
    while True:
        await asyncio.sleep(6 * 60 * 60)
        await asyncio.to_thread(db.privacy_maintenance, ASSESSMENT_RETENTION_DAYS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    maintenance_task = None
    if not DEMO_MODE:
        validate_data_encryption_key()
        if ADMIN_TOKEN == "change-me-before-production":
            raise RuntimeError("ADMIN_TOKEN must be configured before production")
    db.init_db()
    if not DEMO_MODE:
        db.privacy_maintenance(ASSESSMENT_RETENTION_DAYS)
        maintenance_task = asyncio.create_task(_privacy_maintenance_loop())
    try:
        yield
    finally:
        if maintenance_task:
            maintenance_task.cancel()


app = FastAPI(
    title="There Is Another Path — The Path Finder",
    version="1.5.0-prelaunch-ready",
    description="Path Finder commercial MVP + explainable recommendation engine.",
    lifespan=lifespan,
    docs_url="/docs" if EXPOSE_API_DOCS else None,
    redoc_url="/redoc" if EXPOSE_API_DOCS else None,
    openapi_url="/openapi.json" if EXPOSE_API_DOCS else None,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(access_router)
app.include_router(draft_router)

_rate_hits = defaultdict(deque)
_RATE_RULES = {
    "/api/v1/checkout/session": (10, 60),
    "/api/v1/assessments/score": (30, 60),
    "/api/v1/assessments/draft": (60, 60),
}


def _rate_rule(path: str):
    if path == "/api/v1/assessments/submit":
        return (10, 60)
    if path.startswith("/api/v1/feedback/"):
        return (20, 60)
    if path == "/api/v1/privacy/delete":
        return (5, 60)
    if path.startswith("/api/v1/access/switch/"):
        return (20, 60)
    return _RATE_RULES.get(path)


@app.middleware("http")
async def basic_rate_limit(request: Request, call_next):
    if request.method == "POST":
        rule = _rate_rule(request.url.path)
        if rule:
            forwarded = request.headers.get("x-forwarded-for", "")
            ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
            key = (ip, request.url.path.split("/feedback/")[0])
            limit, window = rule
            now = time.monotonic()
            q = _rate_hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return JSONResponse(
                    {"detail": "Too many requests. Please wait and try again."},
                    status_code=429,
                    headers={"Retry-After": str(window)},
                )
            q.append(now)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "script-src 'self' https://connect.facebook.net; "
        "script-src-attr 'none'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https://www.facebook.com; "
        "connect-src 'self' https://www.facebook.com https://connect.facebook.net; "
        "form-action 'self'; "
    )
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

    private_path = (
        request.url.path == "/start"
        or request.url.path == "/report"
        or request.url.path.startswith("/report/")
        or request.url.path.startswith("/api/v1/access")
        or request.url.path.startswith("/api/v1/reports")
        or request.url.path.startswith("/api/v1/privacy")
        or request.url.path.startswith("/api/v1/assessments/draft")
    )
    if private_path:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def page(name: str) -> FileResponse:
    return FileResponse(STATIC / name)


@app.get("/", include_in_schema=False)
def landing():
    return page("index.html")


@app.get("/start", include_in_schema=False)
def start(request: Request, token: str | None = None):
    # One-release migration path for old paid links. New links never expose the token.
    if token:
        purchase = db.get_purchase_by_token(token)
        if not purchase or not purchase_access(purchase)["valid"]:
            return RedirectResponse("/", status_code=303)
        response = RedirectResponse("/start", status_code=303)
        _set_access_cookie(response, request, purchase["id"])
        return response
    return page("assessment.html")


@app.get("/report", include_in_schema=False)
def report_page():
    return page("report.html")


@app.get("/report/{token}", include_in_schema=False)
def legacy_report_page(request: Request, token: str):
    purchase = db.get_purchase_by_token(token)
    if not purchase or not purchase_access(purchase)["valid"]:
        return RedirectResponse("/", status_code=303)
    response = RedirectResponse("/report", status_code=303)
    _set_access_cookie(response, request, purchase["id"])
    return response


@app.get("/privacy", include_in_schema=False)
def privacy():
    return page("privacy.html")


@app.get("/terms", include_in_schema=False)
def terms():
    return page("terms.html")


@app.get("/refunds", include_in_schema=False)
def refunds():
    return page("refunds.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return page("admin.html")


@app.get("/logout", include_in_schema=False)
def logout():
    response = RedirectResponse("/", status_code=303)
    _clear_access_cookie(response)
    return response


@app.get("/health")
def health():
    data = load_paths()
    return {
        "status": "ok",
        "app_version": "1.5.0-prelaunch-ready",
        "engine_version": "1.0.0",
        "consultation_version": CONSULTATION_VERSION,
        "market_version": data["market_version"],
        "path_count": len(data["paths"]),
        "access_days": ASSESSMENT_RETENTION_DAYS,
        "demo_mode": DEMO_MODE,
    }


@app.get("/api/v1/config/public")
def public_config():
    return {
        "product_price_usd": PRODUCT_PRICE_USD,
        "demo_mode": DEMO_MODE,
        "meta_pixel_id": META_PIXEL_ID,
        "support_email": SUPPORT_EMAIL,
        "refund_days": REFUND_DAYS,
        "billing_label": BILLING_LABEL,
        "access_days": ASSESSMENT_RETENTION_DAYS,
    }


@app.get("/api/v1/assessment/schema")
def assessment_schema():
    return json.loads((APP_DIR / "data" / "questions.json").read_text(encoding="utf-8"))


@app.get("/api/v1/paths")
def paths():
    data = load_paths()
    return {
        "version": data["version"],
        "market_version": data["market_version"],
        "paths": [
            {
                "id": p["id"],
                "name": p["name"],
                "family": p["family"],
                "description": p["description"],
            }
            for p in data["paths"]
        ],
    }


@app.post("/api/v1/assessments/score", response_model=AssessmentResult)
def score_assessment(assessment: AssessmentInput):
    try:
        return evaluate(assessment)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Engine error: {exc}") from exc


class CheckoutRequest(BaseModel):
    email: str | None = Field(default=None, max_length=250)
    acquisition: dict = Field(default_factory=dict)


@app.post("/api/v1/checkout/session")
def checkout_session(payload: CheckoutRequest):
    try:
        return create_checkout(payload.acquisition, payload.email)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Checkout error: {exc}") from exc


@app.get("/checkout/success", include_in_schema=False)
def checkout_success(request: Request, session_id: str):
    purchase = verify_success(session_id)
    if not purchase:
        return HTMLResponse(
            "<h1>Payment not verified</h1><p>Please contact support if you were charged.</p>",
            status_code=402,
        )
    response = RedirectResponse(url="/start?welcome=1", status_code=303)
    _set_access_cookie(response, request, purchase["id"])
    return response


@app.get("/checkout/demo-success", include_in_schema=False)
def checkout_demo_success(request: Request, token: str):
    if not DEMO_MODE:
        raise HTTPException(404, "Not found")
    purchase = db.get_purchase_by_token(token)
    if not purchase or purchase["status"] != "paid":
        raise HTTPException(403, "Valid paid access is required")
    response = RedirectResponse(url="/start", status_code=303)
    _set_access_cookie(response, request, purchase["id"])
    return response


@app.post("/api/v1/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="stripe-signature")):
    if not stripe_signature:
        raise HTTPException(400, "Missing Stripe signature")
    try:
        event_type = handle_webhook(await request.body(), stripe_signature)
    except Exception as exc:
        raise HTTPException(400, f"Webhook error: {exc}") from exc
    return {"received": True, "type": event_type}


@app.post("/api/v1/assessments/submit")
def submit_assessment(request: Request, assessment: AssessmentInput):
    purchase = _paid_purchase_from_request(request)
    if db.get_assessment_for_purchase(purchase["id"]):
        raise HTTPException(409, "This purchase already has a completed consultation")
    try:
        result = evaluate(assessment)
        result_payload = result.model_dump()
        previous = db.get_recent_consultation_texts(limit=500)
        answers_payload = assessment.model_dump()

        saved_unique = False
        for attempt in range(4):
            consultation = compose_unique_consultation(
                answers_payload,
                result_payload,
                purchase["id"],
                previous,
                variant_offset=attempt * 128,
            )
            result_payload["_consultation"] = consultation
            try:
                db.save_assessment(
                    purchase["id"],
                    answers_payload,
                    result_payload,
                    consultation_fingerprint=consultation["fingerprint"],
                    consultation_fragment_fingerprints=consultation_fragment_hashes(consultation),
                )
                saved_unique = True
                break
            except db.DuplicateConsultationFingerprint:
                continue

        if not saved_unique:
            raise RuntimeError("Could not produce a unique consultation")

        return {"ok": True, "report_url": "/report"}
    except Exception as exc:
        raise HTTPException(500, f"Engine error: {exc}") from exc


@app.get("/api/v1/reports/me")
def report_data(request: Request):
    purchase = _paid_purchase_from_request(request)
    saved = db.get_assessment_for_purchase(purchase["id"])
    if not saved:
        raise HTTPException(404, "Assessment not completed")
    return build_report(saved["answers"], saved["result"])


class FeedbackDetails(BaseModel):
    status: Literal["not_started", "started", "meaningful_progress", "changed_path"]
    note: str = Field(max_length=1000)

    @field_validator("note")
    @classmethod
    def protect_feedback_text(cls, value: str):
        return validate_free_text(value)


class FeedbackPayload(BaseModel):
    payload: FeedbackDetails


@app.post("/api/v1/feedback/{day}")
def feedback(request: Request, day: int, body: FeedbackPayload):
    if day not in {7, 14, 30}:
        raise HTTPException(400, "Feedback day must be 7, 14, or 30")
    purchase = _paid_purchase_from_request(request)
    db.save_feedback(purchase["id"], day, body.payload.model_dump())
    return {"ok": True}


@app.post("/api/v1/privacy/delete")
def delete_private_data(request: Request):
    purchase = _paid_purchase_from_request(request)
    db.delete_personal_data(purchase["id"])
    response = JSONResponse({"ok": True})
    _clear_access_cookie(response)
    return response


@app.get("/api/v1/admin/summary")
def admin_summary(x_admin_token: str | None = Header(default=None)):
    supplied = x_admin_token or ""
    expected = ADMIN_TOKEN or ""
    if not expected or not secrets.compare_digest(supplied, expected):
        raise HTTPException(403, "Invalid admin token")
    return db.admin_summary()
