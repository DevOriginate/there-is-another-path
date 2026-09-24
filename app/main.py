from __future__ import annotations
import json, time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import AssessmentInput, AssessmentResult
from .engine import evaluate, load_paths
from . import db
from .payments import create_checkout, verify_success, handle_webhook
from .reporting import build_report
from .config import PRODUCT_PRICE_USD, DEMO_MODE, META_PIXEL_ID, ADMIN_TOKEN, SUPPORT_EMAIL, REFUND_DAYS, BILLING_LABEL

APP_DIR = Path(__file__).resolve().parent
STATIC = APP_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

app = FastAPI(title='There Is Another Path — The Path Finder', version='1.2.0', description='Path Finder commercial MVP + explainable recommendation engine.', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=STATIC), name='static')

_rate_hits = defaultdict(deque)
_RATE_RULES = {'/api/v1/checkout/session': (10, 60), '/api/v1/assessments/score': (30, 60)}

def _rate_rule(path: str):
    if path.startswith('/api/v1/assessments/submit/'): return (10, 60)
    if path.startswith('/api/v1/feedback/'): return (20, 60)
    return _RATE_RULES.get(path)

@app.middleware('http')
async def basic_rate_limit(request: Request, call_next):
    if request.method == 'POST':
        rule = _rate_rule(request.url.path)
        if rule:
            forwarded = request.headers.get('x-forwarded-for', '')
            ip = forwarded.split(',')[0].strip() if forwarded else (request.client.host if request.client else 'unknown')
            key = (ip, request.url.path.split('/submit/')[0].split('/feedback/')[0])
            limit, window = rule
            now = time.monotonic()
            q = _rate_hits[key]
            while q and now - q[0] > window: q.popleft()
            if len(q) >= limit:
                return JSONResponse({'detail':'Too many requests. Please wait and try again.'}, status_code=429, headers={'Retry-After':str(window)})
            q.append(now)
    return await call_next(request)

@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.url.path.startswith('/report/'):
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response

def page(name: str) -> FileResponse:
    return FileResponse(STATIC / name)

@app.get('/', include_in_schema=False)
def landing(): return page('index.html')
@app.get('/start', include_in_schema=False)
def start(): return page('assessment.html')
@app.get('/report/{token}', include_in_schema=False)
def report_page(token: str): return page('report.html')
@app.get('/privacy', include_in_schema=False)
def privacy(): return page('privacy.html')
@app.get('/terms', include_in_schema=False)
def terms(): return page('terms.html')
@app.get('/refunds', include_in_schema=False)
def refunds(): return page('refunds.html')
@app.get('/admin', include_in_schema=False)
def admin_page(): return page('admin.html')

@app.get('/health')
def health():
    data=load_paths()
    return {'status':'ok','app_version':'1.2.0','engine_version':'1.0.0','market_version':data['market_version'],'path_count':len(data['paths']),'demo_mode':DEMO_MODE}

@app.get('/api/v1/config/public')
def public_config():
    return {'product_price_usd': PRODUCT_PRICE_USD, 'demo_mode': DEMO_MODE, 'meta_pixel_id': META_PIXEL_ID, 'support_email': SUPPORT_EMAIL, 'refund_days': REFUND_DAYS, 'billing_label': BILLING_LABEL}

@app.get('/api/v1/assessment/schema')
def assessment_schema():
    return json.loads((APP_DIR/'data'/'questions.json').read_text(encoding='utf-8'))

@app.get('/api/v1/paths')
def paths():
    data=load_paths()
    return {'version':data['version'],'market_version':data['market_version'],'paths':[{'id':p['id'],'name':p['name'],'family':p['family'],'description':p['description']} for p in data['paths']]}

@app.post('/api/v1/assessments/score', response_model=AssessmentResult)
def score_assessment(assessment: AssessmentInput):
    try: return evaluate(assessment)
    except Exception as e: raise HTTPException(status_code=500, detail=f'Engine error: {e}')

class CheckoutRequest(BaseModel):
    email: str | None = Field(default=None, max_length=250)
    acquisition: dict = Field(default_factory=dict)

@app.post('/api/v1/checkout/session')
def checkout_session(payload: CheckoutRequest):
    try: return create_checkout(payload.acquisition, payload.email)
    except Exception as e: raise HTTPException(status_code=500, detail=f'Checkout error: {e}')

@app.get('/checkout/success', include_in_schema=False)
def checkout_success(session_id: str):
    purchase = verify_success(session_id)
    if not purchase: return HTMLResponse('<h1>Payment not verified</h1><p>Please contact support if you were charged.</p>', status_code=402)
    return RedirectResponse(url=f"/start?token={purchase['access_token']}&purchase=1", status_code=303)

@app.post('/api/v1/stripe/webhook')
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias='stripe-signature')):
    if not stripe_signature: raise HTTPException(400, 'Missing Stripe signature')
    try: event_type = handle_webhook(await request.body(), stripe_signature)
    except Exception as e: raise HTTPException(400, f'Webhook error: {e}')
    return {'received': True, 'type': event_type}

@app.get('/api/v1/access/{token}')
def access_status(token: str):
    purchase = db.get_purchase_by_token(token)
    if not purchase or purchase['status'] != 'paid': raise HTTPException(403, 'Valid paid access is required')
    assessment = db.get_assessment_for_purchase(purchase['id'])
    return {'valid': True, 'completed': bool(assessment), 'report_url': f'/report/{token}' if assessment else None}

@app.post('/api/v1/assessments/submit/{token}')
def submit_assessment(token: str, assessment: AssessmentInput):
    purchase = db.get_purchase_by_token(token)
    if not purchase or purchase['status'] != 'paid': raise HTTPException(403, 'Valid paid access is required')
    try:
        result = evaluate(assessment)
        db.save_assessment(purchase['id'], assessment.model_dump(), result.model_dump())
        return {'ok': True, 'report_url': f'/report/{token}'}
    except Exception as e: raise HTTPException(500, f'Engine error: {e}')

@app.get('/api/v1/reports/{token}')
def report_data(token: str):
    purchase = db.get_purchase_by_token(token)
    if not purchase or purchase['status'] != 'paid': raise HTTPException(403, 'Valid paid access is required')
    saved = db.get_assessment_for_purchase(purchase['id'])
    if not saved: raise HTTPException(404, 'Assessment not completed')
    return build_report(saved['answers'], saved['result'])

class FeedbackPayload(BaseModel):
    payload: dict

@app.post('/api/v1/feedback/{token}/{day}')
def feedback(token: str, day: int, body: FeedbackPayload):
    if day not in {7,14,30}: raise HTTPException(400, 'Feedback day must be 7, 14, or 30')
    purchase = db.get_purchase_by_token(token)
    if not purchase or purchase['status'] != 'paid': raise HTTPException(403, 'Valid paid access is required')
    db.save_feedback(purchase['id'], day, body.payload)
    return {'ok': True}

@app.get('/api/v1/admin/summary')
def admin_summary(x_admin_token: str | None = Header(default=None)):
    if x_admin_token != ADMIN_TOKEN: raise HTTPException(403, 'Invalid admin token')
    return db.admin_summary()
