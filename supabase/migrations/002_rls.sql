-- ─────────────────────────────────────────────────────────────
-- Retail Expansion AI — RLS Policies
-- Run AFTER 001_schema.sql in Supabase → SQL Editor → Run
-- ─────────────────────────────────────────────────────────────
-- Strategy: all tables are publicly readable (frontend can fetch),
-- but only the service role (backend) can insert/update/delete.
-- ─────────────────────────────────────────────────────────────

-- Enable RLS on every table
ALTER TABLE analysis_runs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE demographics_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE tract_snapshots        ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitor_stores      ENABLE ROW LEVEL SECURITY;
ALTER TABLE parcel_summaries       ENABLE ROW LEVEL SECURITY;
ALTER TABLE parcels                ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools                ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_summaries      ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_points         ENABLE ROW LEVEL SECURITY;
ALTER TABLE neighborhoods          ENABLE ROW LEVEL SECURITY;


-- ── Public READ for all tables (frontend uses anon key to fetch) ──

CREATE POLICY "public can read analysis_runs"          ON analysis_runs          FOR SELECT USING (true);
CREATE POLICY "public can read demographics_summaries" ON demographics_summaries FOR SELECT USING (true);
CREATE POLICY "public can read tract_snapshots"        ON tract_snapshots        FOR SELECT USING (true);
CREATE POLICY "public can read competitor_stores"      ON competitor_stores      FOR SELECT USING (true);
CREATE POLICY "public can read parcel_summaries"       ON parcel_summaries       FOR SELECT USING (true);
CREATE POLICY "public can read parcels"                ON parcels                FOR SELECT USING (true);
CREATE POLICY "public can read schools"                ON schools                FOR SELECT USING (true);
CREATE POLICY "public can read traffic_summaries"      ON traffic_summaries      FOR SELECT USING (true);
CREATE POLICY "public can read traffic_points"         ON traffic_points         FOR SELECT USING (true);
CREATE POLICY "public can read neighborhoods"          ON neighborhoods          FOR SELECT USING (true);


-- ── Service role WRITE (backend FastAPI uses service key to insert) ──
-- The service role bypasses RLS entirely by default in Supabase,
-- so no explicit write policy is needed for it. These are here for clarity.

-- That's it — frontend reads freely, only your backend can write.
