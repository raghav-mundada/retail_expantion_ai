"""
RetailIQ — Stripe Billing API
Endpoints:
  POST /billing/checkout      Create a Stripe Checkout Session → returns {url}
  POST /billing/portal        Create a Stripe Customer Portal Session → returns {url}
  POST /billing/webhook       Stripe webhook handler (raw body, signature verified)

All database writes go through Supabase via the service-role key.
No profile mutations are permitted from the frontend directly.
"""
import json
import logging
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# ── Stripe client (lazy-initialized per request) ─────────────────────────────

def _stripe_client() -> stripe.StripeClient:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured on this server.",
        )
    return stripe.StripeClient(api_key=settings.stripe_secret_key)


# ── Supabase REST helper (service-role) ──────────────────────────────────────

def _supa_headers() -> dict:
    s = get_settings()
    return {
        "apikey": s.supabase_service_key,
        "Authorization": f"Bearer {s.supabase_service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supa_url(path: str) -> str:
    return f"{get_settings().supabase_url}/rest/v1{path}"


def _profile_by_user_id(user_id: str) -> Optional[dict]:
    import requests as req
    r = req.get(
        _supa_url(f"/profiles?id=eq.{user_id}&select=*"),
        headers=_supa_headers(),
        timeout=8,
    )
    rows = r.json()
    return rows[0] if rows else None


def _profile_by_customer_id(customer_id: str) -> Optional[dict]:
    import requests as req
    r = req.get(
        _supa_url(f"/profiles?stripe_customer_id=eq.{customer_id}&select=*"),
        headers=_supa_headers(),
        timeout=8,
    )
    rows = r.json()
    return rows[0] if rows else None


def _profile_by_subscription_id(sub_id: str) -> Optional[dict]:
    import requests as req
    r = req.get(
        _supa_url(f"/profiles?stripe_subscription_id=eq.{sub_id}&select=*"),
        headers=_supa_headers(),
        timeout=8,
    )
    rows = r.json()
    return rows[0] if rows else None


def _update_profile(user_id: str, patch: dict) -> None:
    import requests as req
    r = req.patch(
        _supa_url(f"/profiles?id=eq.{user_id}"),
        headers=_supa_headers(),
        json=patch,
        timeout=8,
    )
    if r.status_code not in (200, 204):
        logger.error("[Billing] Profile update failed: %s — %s", r.status_code, r.text[:200])


# ── Auth dependency — verify Supabase JWT ────────────────────────────────────

async def _require_auth(authorization: str = Header(default="")) -> str:
    """
    Validates the Supabase Bearer token sent by the frontend.
    Returns the user's UUID on success.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()
    settings = get_settings()

    import requests as req
    r = req.get(
        f"{settings.supabase_url}/auth/v1/user",
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=8,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    data = r.json()
    uid = data.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Could not identify user.")
    return uid


# ── Request / Response schemas ───────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    price_id: str          # Stripe price ID (pro_monthly or pro_annual)
    billing_interval: str  # "monthly" | "annual"


class PortalRequest(BaseModel):
    pass   # customer_id is looked up from the authenticated user's profile


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


# ── POST /billing/checkout ────────────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    user_id: str = Depends(_require_auth),
) -> CheckoutResponse:
    """
    Creates a Stripe Checkout Session for the authenticated user.
    Passes user_id via client_reference_id so the webhook can map
    the completed payment back to the correct Supabase profile.
    """
    settings = get_settings()
    client   = _stripe_client()

    profile  = _profile_by_user_id(user_id)
    existing_customer_id: Optional[str] = profile.get("stripe_customer_id") if profile else None

    session_params: dict = {
        "mode": "subscription",
        "line_items": [{"price": body.price_id, "quantity": 1}],
        "client_reference_id": user_id,
        "success_url": f"{settings.frontend_url}/billing?checkout=success",
        "cancel_url":  f"{settings.frontend_url}/pricing?checkout=cancel",
        "allow_promotion_codes": True,
        "subscription_data": {
            "metadata": {"user_id": user_id},
            # 7-day trial for users without an existing subscription
            "trial_period_days": 7 if (not existing_customer_id) else 0,
        },
        "metadata": {"user_id": user_id},
    }

    # Re-use existing Stripe customer so payment methods are remembered
    if existing_customer_id:
        session_params["customer"] = existing_customer_id
    elif profile and profile.get("email"):
        session_params["customer_email"] = profile["email"]

    try:
        session = client.checkout.sessions.create(params=session_params)
        return CheckoutResponse(url=session.url)
    except stripe.StripeError as exc:
        logger.error("[Billing] Checkout creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── POST /billing/portal ─────────────────────────────────────────────────────

@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    user_id: str = Depends(_require_auth),
) -> PortalResponse:
    """
    Generates a Stripe Customer Portal URL for the authenticated user
    so they can update payment details or cancel their subscription.
    """
    settings = get_settings()
    client   = _stripe_client()

    profile  = _profile_by_user_id(user_id)
    customer_id = profile.get("stripe_customer_id") if profile else None

    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer found. Please subscribe first.",
        )

    try:
        session = client.billing_portal.sessions.create(params={
            "customer": customer_id,
            "return_url": f"{settings.frontend_url}/billing",
        })
        return PortalResponse(url=session.url)
    except stripe.StripeError as exc:
        logger.error("[Billing] Portal creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── POST /billing/webhook ─────────────────────────────────────────────────────

@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
) -> JSONResponse:
    """
    Stripe webhook — verified with STRIPE_WEBHOOK_SECRET.
    All Supabase profile mutations happen here; never from the frontend.

    Handled events:
      checkout.session.completed        → record customer/subscription IDs, set plan
      customer.subscription.updated     → update period_end, cancel_at_period_end
      customer.subscription.deleted     → downgrade to free, clear Stripe fields
    """
    settings = get_settings()

    if not settings.stripe_webhook_secret:
        logger.warning("[Webhook] STRIPE_WEBHOOK_SECRET not set — skipping signature check")
        payload_bytes = await request.body()
        try:
            event = stripe.Event.construct_from(
                json.loads(payload_bytes), stripe.api_key
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        payload_bytes = await request.body()
        try:
            event = stripe.Webhook.construct_event(
                payload_bytes,
                stripe_signature,
                settings.stripe_webhook_secret,
            )
        except stripe.SignatureVerificationError as exc:
            logger.warning("[Webhook] Signature verification failed: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid signature.") from exc

    etype = event["type"]
    data  = event["data"]["object"]
    logger.info("[Webhook] Received: %s", etype)

    # ── checkout.session.completed ────────────────────────────────────────────
    if etype == "checkout.session.completed":
        user_id     = data.get("client_reference_id") or (data.get("metadata") or {}).get("user_id")
        customer_id = data.get("customer")
        sub_id      = data.get("subscription")

        if not user_id:
            logger.error("[Webhook] checkout.session.completed — no user_id in metadata")
            return JSONResponse({"ok": True})

        patch: dict = {"plan": "pro"}
        if customer_id:
            patch["stripe_customer_id"] = customer_id
        if sub_id:
            patch["stripe_subscription_id"] = sub_id

        # Retrieve full subscription to get period_end + trial_end
        if sub_id and settings.stripe_secret_key:
            try:
                sub = stripe.Subscription.retrieve(
                    sub_id,
                    api_key=settings.stripe_secret_key,
                )
                period_end = sub.get("current_period_end")
                trial_end  = sub.get("trial_end")
                if period_end:
                    from datetime import datetime, timezone
                    patch["subscription_period_end"] = datetime.fromtimestamp(
                        period_end, tz=timezone.utc
                    ).isoformat()
                if trial_end:
                    patch["subscription_start_date"] = datetime.fromtimestamp(
                        trial_end, tz=timezone.utc
                    ).isoformat()
                else:
                    from datetime import datetime, timezone
                    patch["subscription_start_date"] = datetime.utcnow().isoformat()
            except stripe.StripeError:
                pass

        _update_profile(user_id, patch)
        logger.info("[Webhook] checkout.session.completed → user %s upgraded to pro", user_id)

    # ── customer.subscription.updated ────────────────────────────────────────
    elif etype == "customer.subscription.updated":
        customer_id  = data.get("customer")
        sub_id       = data.get("id")
        period_end   = data.get("current_period_end")
        cancel_end   = data.get("cancel_at_period_end", False)
        status_value = data.get("status", "")

        profile = _profile_by_customer_id(customer_id) if customer_id else None
        if not profile:
            profile = _profile_by_subscription_id(sub_id) if sub_id else None
        if not profile:
            logger.warning("[Webhook] subscription.updated — profile not found for customer %s", customer_id)
            return JSONResponse({"ok": True})

        patch = {"subscription_cancel_at_period_end": cancel_end}
        if period_end:
            from datetime import datetime, timezone
            patch["subscription_period_end"] = datetime.fromtimestamp(
                period_end, tz=timezone.utc
            ).isoformat()
        # If subscription was reactivated after cancellation
        if status_value == "active" and not cancel_end:
            patch["plan"] = "pro"

        _update_profile(profile["id"], patch)
        logger.info("[Webhook] subscription.updated → user %s cancel_at_end=%s", profile["id"], cancel_end)

    # ── customer.subscription.deleted ────────────────────────────────────────
    elif etype == "customer.subscription.deleted":
        customer_id = data.get("customer")
        sub_id      = data.get("id")

        profile = _profile_by_customer_id(customer_id) if customer_id else None
        if not profile:
            profile = _profile_by_subscription_id(sub_id) if sub_id else None
        if not profile:
            logger.warning("[Webhook] subscription.deleted — profile not found for customer %s", customer_id)
            return JSONResponse({"ok": True})

        _update_profile(profile["id"], {
            "plan":                           "free",
            "stripe_subscription_id":         None,
            "subscription_period_end":        None,
            "subscription_cancel_at_period_end": False,
        })
        logger.info("[Webhook] subscription.deleted → user %s downgraded to free", profile["id"])

    return JSONResponse({"ok": True})
