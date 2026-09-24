from __future__ import annotations
from . import db
from .config import *

def create_checkout(acquisition: dict, email: str | None = None) -> dict:
    amount = PRODUCT_PRICE_USD * 100
    if DEMO_MODE or not STRIPE_SECRET_KEY:
        purchase = db.create_purchase(amount, acquisition, email, status="paid")
        return {"mode":"demo", "url": f"{PUBLIC_BASE_URL}/start?token={purchase['access_token']}", "access_token": purchase['access_token']}
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    purchase = db.create_purchase(amount, acquisition, email, status="pending")
    kwargs = dict(
        mode="payment",
        success_url=f"{PUBLIC_BASE_URL}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_BASE_URL}/?checkout=cancelled",
        client_reference_id=str(purchase['id']),
        metadata={"purchase_id": str(purchase['id']), "access_token": purchase['access_token']},
        allow_promotion_codes=True,
    )
    if STRIPE_PRICE_ID:
        kwargs["line_items"] = [{"price": STRIPE_PRICE_ID, "quantity": 1}]
    else:
        kwargs["line_items"] = [{
            "price_data": {"currency":"usd","unit_amount":amount,"product_data":{"name":PRODUCT_NAME,"description":"Personalized path assessment + 30-day action plan"}},
            "quantity":1,
        }]
    if email: kwargs["customer_email"] = email
    session = stripe.checkout.Session.create(**kwargs)
    db.set_stripe_session(purchase['id'], session.id)
    return {"mode":"stripe", "url": session.url}

def verify_success(session_id: str) -> dict | None:
    purchase = db.get_purchase_by_session(session_id)
    if not purchase: return None
    if purchase['status'] == 'paid': return purchase
    if not STRIPE_SECRET_KEY: return None
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status == 'paid':
        email = None
        try: email = session.customer_details.email
        except Exception: pass
        db.mark_paid_by_session(session_id, email)
        return db.get_purchase_by_session(session_id)
    return None

def handle_webhook(payload: bytes, signature: str):
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook is not configured")
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        if session.get('payment_status') == 'paid':
            email = (session.get('customer_details') or {}).get('email')
            db.mark_paid_by_session(session['id'], email)
    return event['type']
