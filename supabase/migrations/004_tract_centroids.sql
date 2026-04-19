-- ─────────────────────────────────────────────────────────────
-- Retail Expansion AI — Tract centroids for spatial scoring
-- Run AFTER 003_agents.sql in Supabase → SQL Editor → Run
-- ─────────────────────────────────────────────────────────────
--
-- The TIGERweb API gives us centroid lat/lon for every census tract,
-- but our original schema dropped them. The scout needs these to
-- compute parcel-relative demographics (pop_1km, income_1km, huff).
-- Adding them as nullable so existing rows aren't broken; new runs
-- will populate them.
-- ─────────────────────────────────────────────────────────────

ALTER TABLE tract_snapshots
    ADD COLUMN IF NOT EXISTS centroid_lat FLOAT8,
    ADD COLUMN IF NOT EXISTS centroid_lon FLOAT8;

CREATE INDEX IF NOT EXISTS idx_tract_centroid
    ON tract_snapshots(run_id, centroid_lat, centroid_lon);
