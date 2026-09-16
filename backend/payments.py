import os
import json
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient

payments_router = APIRouter()
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ.get("DB_NAME", "app")]
payment_transactions = db["payment_transactions"]

SMP_COUNTRIES = {
    "AU", "AT", "BE", "BG", "CA", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GI", "GR",
    "HK", "HU", "IE", "IT", "JP", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO",
    "SG", "SK", "SI", "ES", "SE", "CH", "GB", "US",
}

PLAN_BY_LOOKUP_PREFIX = {
    "starter": "starter",
    "pro": "pro",
    "agency": "agency",
}

_tax_mode_cache: Optional[str] = None

def get_tax_mode() -> str:
    global _tax_mode_cache
    if _tax_mode_cache:
        return _tax_mode_cache
    try:
        country = stripe.Account.retrieve()["country"]
        _tax_mode_cache = "full" if country in SMP_COUNTRIES else "calc_only"
    except Exception:
        _tax_mode_cache = "calc_only"
    return _tax_mode_cache

def plan_from_lookup_key(lookup_key: str) -> str:
    for prefix, plan in PLAN_BY_LOOKUP_PREFIX.items():
        if lookup_key.startswith(prefix):
            return plan
    return "starter"

class CheckoutRequest(BaseModel):
    lookup_key: str
    quantity: int = Field(1, ge=1, le=100)
    origin_url: str
    user_id: Optional[str] = None

@payments_router.post("/api/payments/checkout")
async def create_checkout(req: CheckoutRequest):
    prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(500, f"Preço não encontrado: {req.lookup_key}")
    price = prices[0]
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": req.quantity}],
        mode="subscription" if price.recurring else "payment",
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        metadata={"user_id": req.user_id or "", "lookup_key": req.lookup_key},
    )
    tax_mode = get_tax_mode()
    if tax_mode == "full":
        try:
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or "").lower()
            if "managed payments" in msg or "ineligible" in msg:
                session = stripe.checkout.Session.create(
                    **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required",
                )
            else:
                raise
    elif tax_mode == "calc_only":
        try:
            session = stripe.checkout.Session.create(
                **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required",
            )
        except stripe.error.InvalidRequestError as e:
            if "tax" in (e.user_message or str(e)).lower():
                session = stripe.checkout.Session.create(**kwargs)
            else:
                raise
    else:
        session = stripe.checkout.Session.create(**kwargs)
    await payment_transactions.insert_one({
        "session_id": session.id, "user_id": req.user_id, "lookup_key": req.lookup_key,
        "amount": (price.unit_amount or 0) * req.quantity, "currency": price.currency,
        "status": "initiated", "payment_status": "pending",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return {"checkout_url": session.url, "session_id": session.id}

async def mark_paid(session_id: str, subscription=None, payment_intent=None, payment_status="paid"):
    result = await payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": payment_status,
                  "stripe_subscription_id": subscription,
                  "stripe_payment_intent_id": payment_intent,
                  "updated_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count:
        record = await payment_transactions.find_one({"session_id": session_id})
        if record and record.get("user_id"):
            plan = plan_from_lookup_key(record.get("lookup_key", ""))
            await db.users.update_one({"user_id": record["user_id"]}, {"$set": {"plan": plan}})

@payments_router.get("/api/payments/status/{session_id}")
async def get_status(session_id: str):
    record = await payment_transactions.find_one({"session_id": session_id})
    if not record:
        raise HTTPException(404, "Transação não encontrada")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await mark_paid(session_id, s.subscription, s.payment_intent)
                record = await payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"],
            "payment_status": record["payment_status"]}

@payments_router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Assinatura inválida")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        await mark_paid(obj["id"], obj.get("subscription"), obj.get("payment_intent"),
                        obj.get("payment_status", "paid"))
    elif t == "checkout.session.async_payment_succeeded":
        await payment_transactions.update_one({"session_id": obj["id"]},
            {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc)}})
    elif t == "checkout.session.async_payment_failed":
        await payment_transactions.update_one({"session_id": obj["id"]},
            {"$set": {"status": "failed", "payment_status": "failed", "updated_at": datetime.now(timezone.utc)}})
    elif t == "checkout.session.expired":
        await payment_transactions.update_one({"session_id": obj["id"]},
            {"$set": {"status": "expired", "payment_status": "expired", "updated_at": datetime.now(timezone.utc)}})
    elif t == "charge.refunded":
        await payment_transactions.update_one({"stripe_payment_intent_id": obj.get("payment_intent")},
            {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": datetime.now(timezone.utc)}})
    return {"status": "ok"}

@payments_router.get("/api/payments/plans")
async def list_plans():
    plans = []
    for lookup_key in ["starter_monthly", "starter_yearly", "pro_monthly", "pro_yearly", "agency_monthly", "agency_yearly"]:
        prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data
        if prices:
            p = prices[0]
            plans.append({"lookup_key": lookup_key, "amount": p.unit_amount, "currency": p.currency,
                          "interval": p.recurring.interval if p.recurring else None})
    return plans
