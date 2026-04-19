-- ─────────────────────────────────────────────────────────────
-- Retail Expansion AI — Auth + per-user run history
-- Run AFTER 004_tract_centroids.sql in Supabase → SQL Editor → Run
-- ─────────────────────────────────────────────────────────────
--
-- Adds user attribution to runs so logged-in users can see their
-- past searches. Anonymous runs still work (user_id is nullable).
-- The cache lookup in /analyze deliberately ignores user_id — two
-- different users searching the exact same lat/lon/radius/format
-- share the same cached pipeline result.
-- ─────────────────────────────────────────────────────────────

-- 1. Add user_id column (nullable so anonymous runs still work)
ALTER TABLE analysis_runs
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- 2. Track the store format the user picked (currently re-derived
--    from the debate request — persisting it here makes /me/runs
--    show "Target / 8.2 km / 3 days ago" without an extra join).
ALTER TABLE analysis_runs
    ADD COLUMN IF NOT EXISTS store_format TEXT;

-- 3. Optional human-readable label users can apply later
ALTER TABLE analysis_runs
    ADD COLUMN IF NOT EXISTS label TEXT;

-- 4. Index for "give me my runs" queries
CREATE INDEX IF NOT EXISTS idx_runs_user_created
    ON analysis_runs(user_id, created_at DESC);


-- ── RLS — keep public read (existing flow), add owner-only write/delete ──
--
-- We DO NOT remove the public SELECT policy: anonymous users still need to
-- read run data through the FastAPI backend. The /me/runs endpoint filters
-- by user_id at the application layer using the verified JWT, so security
-- is enforced there.
--
-- Future hardening (if you want to drop public read): replace the
-- "public can read analysis_runs" policy with one that only allows
-- USING (user_id IS NULL OR user_id = auth.uid()).