-- ─────────────────────────────────────────────────────────────
-- Retail Expansion AI — Supabase Schema
-- Run this entire file in Supabase → SQL Editor → Run
-- ─────────────────────────────────────────────────────────────


-- 1. Parent: one row per pipeline run (lat/lon/radius combo)
CREATE TABLE IF NOT EXISTS analysis_runs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lat         FLOAT8 NOT NULL,
    lon         FLOAT8 NOT NULL,
    radius_km   FLOAT8 NOT NULL,
    fetched_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (lat, lon, radius_km)
);


-- 2. Demographics rolled summary (1:1 with run)
CREATE TABLE IF NOT EXISTS demographics_summaries (
    run_id                  UUID PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
    tract_count             INT,
    total_population        INT,
    total_households        INT,
    median_hh_income_avg    NUMERIC,
    avg_poverty_rate        NUMERIC,
    avg_owner_share         NUMERIC,
    avg_renter_share        NUMERIC
);


-- 3. Individual census tracts (~190 rows per run)
CREATE TABLE IF NOT EXISTS tract_snapshots (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    tract_geoid      TEXT,
    name             TEXT,
    dist_km          NUMERIC,
    total_population INT,
    total_households INT,
    median_hh_income NUMERIC,
    owner_share      NUMERIC,
    renter_share     NUMERIC,
    poverty_rate     NUMERIC,
    UNIQUE (run_id, tract_geoid)
);


-- 4. Competitor stores from Geoapify (~119 rows per run)
CREATE TABLE IF NOT EXISTS competitor_stores (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    place_id    TEXT,
    name        TEXT,
    shop_type   TEXT,
    lat         FLOAT8,
    lon         FLOAT8,
    dist_km     NUMERIC,
    address     TEXT,
    UNIQUE (run_id, place_id)
);


-- 5. Commercial parcel summary (1:1 with run)
CREATE TABLE IF NOT EXISTS parcel_summaries (
    run_id                    UUID PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
    total_count               INT,
    retail_compatible_count   INT,
    avg_parcel_acres          NUMERIC,
    max_parcel_acres          NUMERIC,
    commercial_type_breakdown JSONB
);


-- 6. Commercial parcels (~2143 rows per run)
CREATE TABLE IF NOT EXISTS parcels (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id               UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    pid                  TEXT,
    address              TEXT,
    zip_code             TEXT,
    lat                  FLOAT8,
    lon                  FLOAT8,
    dist_km              NUMERIC,
    land_use_label       TEXT,
    commercial_type      TEXT,
    parcel_acres         NUMERIC,
    is_retail_compatible BOOLEAN,
    market_value         NUMERIC,
    build_year           INT,
    UNIQUE (run_id, pid)
);


-- 7. Schools from Geoapify (~249 rows per run)
CREATE TABLE IF NOT EXISTS schools (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    place_id      TEXT,
    name          TEXT,
    amenity_type  TEXT,
    lat           FLOAT8,
    lon           FLOAT8,
    dist_km       NUMERIC,
    UNIQUE (run_id, place_id)
);


-- 8. Traffic AADT summary (1:1 with run)
CREATE TABLE IF NOT EXISTS traffic_summaries (
    run_id        UUID PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
    point_count   INT,
    nearest_road  TEXT,
    nearest_aadt  INT,
    max_aadt      INT,
    avg_aadt      NUMERIC
);


-- 9. Top 50 AADT traffic points per run
CREATE TABLE IF NOT EXISTS traffic_points (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    street_name   TEXT,
    route_label   TEXT,
    aadt          INT,
    distance_m    NUMERIC,
    lat           FLOAT8,
    lon           FLOAT8
);


-- 10. Neighborhoods (87 rows per run)
CREATE TABLE IF NOT EXISTS neighborhoods (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    neighborhood_id   TEXT,
    neighborhood_name TEXT,
    centroid_lat      FLOAT8,
    centroid_lon      FLOAT8,
    dist_km           NUMERIC,
    in_radius         BOOLEAN,
    UNIQUE (run_id, neighborhood_id)
);


-- ── Indexes for fast agent queries ───────────────────────────
CREATE INDEX IF NOT EXISTS idx_tract_run      ON tract_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_stores_run     ON competitor_stores(run_id);
CREATE INDEX IF NOT EXISTS idx_parcels_run    ON parcels(run_id);
CREATE INDEX IF NOT EXISTS idx_parcels_retail ON parcels(run_id, is_retail_compatible);
CREATE INDEX IF NOT EXISTS idx_schools_run    ON schools(run_id);
CREATE INDEX IF NOT EXISTS idx_traffic_run    ON traffic_points(run_id);
CREATE INDEX IF NOT EXISTS idx_hood_run       ON neighborhoods(run_id);
