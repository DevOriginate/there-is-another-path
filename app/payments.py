from __future__ import annotations

from . import db
from .config import *

_ALLOWED_ACQUISITION_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "landing_variant",
}


def _safe_acquisition(acquisition: dict) -> dict:
    clean = {}
    for key in _ALLOWED_ACQUISITION_KEYS:
        value = acquisition.get(key)
        if value is None:
            continue
        clean[key] = str(value)[:120]
    return clean


def create_checkout(acquisition: dict, email: str | None = None) -> dict:
    amount = PRODUCT_PRICE_USD * 100
    acquisition = _safe_acquisition(acquisition)

    if DEMO_MODE or not STRIPE_SECRET_KEY:
        purchase = db.create_purchase(amount, acquisition, None, status="paid")
        return {
            "mode": "demo",
            "url": f"{PUBLIC_BASE_URL}/checkout/demo-success?token={purchase['access_token']}",
        }

    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
    purchase = db.create_purchase(amount, acquisition, None, status="pending")
    purchase_id = str(purchase["id"])
    kwargs = dict(
        mode="payment",
        success_url=f"{PUBLIC_BASE_URL}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_BASE_URL}/?checkout=cancelled",
        client_reference_id=purchase_id,
        metadata={"purchase_id": purchase_id},
        payment_intent_data={"metadata": {"purchase_id": purchase_id}},
        allow_promotion_codes=True,
    )
    if STRIPE_PRICE_ID:
        kwargs["line_items"] = [{"price": STRIPE_PRICE_ID, "quantity": 1}]
    else:
        kwargs["line_items"] = [
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount,
                    "product_data": {
                        "name": PRODUCT_NAME,
                        "description": "Personalized decision-support consultation + 30-day action plan",
                    },
                },
                "quantity": 1,
            }
        ]
    if email:
        kwargs["customer_email"] = email

    session = stripe.checkout.Session.create(**kwargs)
    db.set_stripe_session(purchase["id"], session.id)
    if getattr(session, "payment_intent", None):
        db.set_payment_intent(purchase["id"], str(session.payment_intent))
    return {"mode": "stripe", "url": session.url}


def verify_success(session_id: str) -> dict | None:
    if not STRIPE_SECRET_KEY:
        return None

    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status != "paid":
        return None

    payment_intent_id = str(session.payment_intent) if session.payment_intent else None
    purchase = db.get_purchase_by_session(session_id)
    if purchase:
        # A refunded/disputed transaction must never be reactivated by a repeated success callback.
        if purchase["status"] in {"refunded", "disputed"}:
            return None
        db.mark_paid_by_session(session_id, payment_intent_id)
        return db.get_purchase_by_session(session_id)

    recovered = db.recover_paid_purchase(
        session_id=session_id,
        access_token=None,
        amount_cents=session.amount_total or PRODUCT_PRICE_USD * 100,
        currency=session.currency or "usd",
        email=None,
        payment_intent_id=payment_intent_id,
    )
    if recovered and recovered["status"] in {"refunded", "disputed"}:
        return None
    return recovered


def _payment_intent_from_dispute(dispute, stripe) -> str | None:
    payment_intent_id = dispute.get("payment_intent")
    if payment_intent_id:
        return str(payment_intent_id)

    charge_id = dispute.get("charge")
    if not charge_id:
        return None
    try:
        charge = stripe.Charge.retrieve(charge_id)
        return str(charge.payment_intent) if charge.payment_intent else None
    except Exception:
        return None


def handle_webhook(payload: bytes, signature: str):
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook is not configured")

    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
    event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        if obj.get("payment_status") == "paid":
            payment_intent_id = str(obj.get("payment_intent")) if obj.get("payment_intent") else None
            purchase = db.get_purchase_by_session(obj["id"])
            if purchase:
                if purchase["status"] not in {"refunded", "disputed"}:
                    db.mark_paid_by_session(obj["id"], payment_intent_id)
            else:
                db.recover_paid_purchase(
                    session_id=obj["id"],
                    access_token=None,
                    amount_cents=obj.get("amount_total") or PRODUCT_PRICE_USD * 100,
                    currency=obj.get("currency") or "usd",
                    email=None,
                    payment_intent_id=payment_intent_id,
                )

    elif event_type == "checkout.session.expired":
        db.mark_checkout_expired(obj["id"])

    elif event_type == "charge.refunded":
        payment_intent_id = obj.get("payment_intent")
        fully_refunded = bool(obj.get("refunded")) or (
            obj.get("amount") is not None
            and obj.get("amount_refunded") is not None
            and int(obj.get("amount_refunded") or 0) >= int(obj.get("amount") or 0)
        )
        if payment_intent_id and fully_refunded:
            db.set_purchase_billing_state(
                str(payment_intent_id),
                status="refunded",
                revoked_reason="refund",
            )

    elif event_type == "charge.dispute.created":
        payment_intent_id = _payment_intent_from_dispute(obj, stripe)
        if payment_intent_id:
            db.set_purchase_billing_state(
                payment_intent_id,
                status="disputed",
                revoked_reason="dispute",
            )

    elif event_type == "charge.dispute.closed":
        payment_intent_id = _payment_intent_from_dispute(obj, stripe)
        if payment_intent_id:
            dispute_status = str(obj.get("status") or "").lower()
            if dispute_status == "won":
                db.set_purchase_billing_state(
                    payment_intent_id,
                    status="paid",
                    revoked_reason=None,
                )
            elif dispute_status in {"lost", "warning_closed"}:
                db.set_purchase_billing_state(
                    payment_intent_id,
                    status="disputed",
                    revoked_reason="dispute_lost",
                )

    return event_type
