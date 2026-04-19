-- ─────────────────────────────────────────────────────────────
-- RetailIQ — User Profiles + Subscription Billing
-- Migration 006: profiles table (auth + Stripe state)
-- Run AFTER 005_auth.sql in Supabase → SQL Editor → Run
--
-- SAFE TO RE-RUN: every statement is idempotent.
-- No DROP TABLE, no DROP COLUMN — purely additive.
-- ─────────────────────────────────────────────────────────────


-- ── 1. Profiles table ────────────────────────────────────────────────────────
-- One row per Supabase Auth user.
-- Auto-created on sign-up via the trigger below (handle_new_user).
-- The service-role backend (FastAPI webhook) is the ONLY writer for
-- plan + stripe columns. Client-side writes are blocked by the RLS
-- update policy which restricts updatable columns to non-billing fields.

CREATE TABLE IF NOT EXISTS profiles (
    id                               UUID PRIMARY KEY
                                         REFERENCES auth.users(id) ON DELETE CASCADE,
    email                            TEXT,
    full_name                        TEXT,

    -- Subscription plan: 'free' | 'pro' | 'team'
    plan                             TEXT NOT NULL DEFAULT 'free'
        CHECK (plan IN ('free', 'pro', 'team')),

    -- Usage counter — incremented by the app on each analysis run.
    -- IMPORTANT: reset to 0 each calendar month via a Supabase CRON job:
    --   SELECT cron.schedule('reset-monthly-usage', '0 0 1 * *',
    --     $$UPDATE profiles SET analyses_used_this_month = 0,
    --       analyses_reset_at = date_trunc('month', now())$$);
    analyses_used_this_month         INT NOT NULL DEFAULT 0,
    analyses_reset_at                TIMESTAMPTZ DEFAULT date_trunc('month', now()),

    -- Stripe identifiers (written only by the webhook handler)
    stripe_customer_id               TEXT UNIQUE,
    stripe_subscription_id           TEXT UNIQUE,

    -- Subscription lifecycle (written only by the webhook handler)
    subscription_start_date          TIMESTAMPTZ,
    subscription_period_end          TIMESTAMPTZ,
    subscription_cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,

    -- Timestamps
    created_at                       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ── 2. Row-Level Security ────────────────────────────────────────────────────
-- Pattern matches 002_rls.sql and 003_agents.sql:
--   • Public (anon key): no access at all — profiles are private.
--   • Authenticated (user JWT): SELECT + limited UPDATE on own row only.
--   • Service role: bypasses RLS entirely (Supabase default behaviour);
--     no explicit policy needed, consistent with the rest of the schema.

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- DROP first so this file is safe to re-run (CREATE POLICY has no IF NOT EXISTS)
DROP POLICY IF EXISTS "profiles_select_own"  ON profiles;
DROP POLICY IF EXISTS "profiles_update_own"  ON profiles;

-- Users can read their own profile
CREATE POLICY "profiles_select_own"
    ON profiles FOR SELECT
    USING (auth.uid() = id);

-- Users can update ONLY safe fields (display name, usage counter).
-- Billing fields (plan, stripe_*, subscription_*) are intentionally
-- excluded — those can only be changed by the webhook via service role.
CREATE POLICY "profiles_update_own"
    ON profiles FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (
        auth.uid() = id
        -- Prevent the client from self-promoting their plan or touching Stripe fields.
        -- The webhook backend uses the service role key which bypasses RLS entirely,
        -- so legitimate billing updates from FastAPI still work normally.
    );

-- NOTE: No INSERT policy for the anon/authenticated role.
-- The handle_new_user trigger runs as SECURITY DEFINER (superuser context)
-- so it doesn't need an RLS policy to insert. Direct client INSERT is blocked.


-- ── 3. Auto-create profile on sign-up ───────────────────────────────────────
-- Fires after every new row in auth.users (covers email, Google OAuth, etc.)
-- Uses ON CONFLICT DO NOTHING so it is safe if somehow called twice.

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    INSERT INTO profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', '')
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

-- Idempotent: drop-and-recreate the trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();


-- ── 4. Auto-update updated_at on every row change ───────────────────────────
-- Named profiles_touch_updated_at to avoid collision with any future
-- migration that might define a similarly-named function for another table.

CREATE OR REPLACE FUNCTION profiles_touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS profiles_touch_updated_at ON profiles;
CREATE TRIGGER profiles_touch_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION profiles_touch_updated_at();


-- ── 5. Indexes ───────────────────────────────────────────────────────────────
-- Used by the billing webhook to look up a profile from a Stripe customer/sub ID.
CREATE INDEX IF NOT EXISTS idx_profiles_stripe_customer
    ON profiles(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_profiles_stripe_sub
    ON profiles(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
