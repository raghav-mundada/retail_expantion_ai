/**
 * Stripe helpers — thin wrappers around the RetailIQ backend billing endpoints.
 * No Stripe publishable key is needed here; all payment logic lives server-side.
 */
const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8003';

export const PLANS = {
  pro: {
    name:         'Pro',
    monthlyPrice: 79,
    annualPrice:  749,
    annualSavings:199,
    features: [
      'Unlimited analyses',
      'AI Simulation — 220 household agents',
      'AI Debate — Bull / Bear / Orchestrator',
      'TinyFish live retail intel',
      'Supabase result persistence',
      'Priority processing',
    ],
    priceIds: {
      monthly: import.meta.env.VITE_STRIPE_PRICE_PRO_MONTHLY ?? '',
      annual:  import.meta.env.VITE_STRIPE_PRICE_PRO_ANNUAL  ?? '',
    },
  },
} as const;

export type BillingInterval = 'monthly' | 'annual';

// ── Create Stripe Checkout Session ───────────────────────────────────────────
export async function createCheckoutSession(
  priceId: string,
  billingInterval: BillingInterval,
  accessToken: string,
): Promise<string> {
  const res = await fetch(`${BASE}/api/billing/checkout`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ price_id: priceId, billing_interval: billingInterval }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail ?? 'Checkout creation failed');
  }

  const { url } = await res.json();
  return url;
}

// ── Create Stripe Customer Portal Session ────────────────────────────────────
export async function createPortalSession(accessToken: string): Promise<string> {
  const res = await fetch(`${BASE}/api/billing/portal`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${accessToken}`,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail ?? 'Portal creation failed');
  }

  const { url } = await res.json();
  return url;
}
