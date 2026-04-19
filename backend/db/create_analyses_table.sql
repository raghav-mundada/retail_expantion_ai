-- RetailIQ: Full database setup
-- Run this in Supabase Dashboard → SQL Editor → New Query

-- ────────────────────────────────────────────────
-- 1. KV Cache table (replaces all local JSON files)
--    Keys: fips:<lat>,<lng>  |  acs:<state>:<county>
-- ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cache (
  key        text PRIMARY KEY,
  value      jsonb NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS cache_key_idx ON cache (key);

-- Allow service-role reads and writes
ALTER TABLE cache ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='cache' AND policyname='cache_service_read') THEN
    CREATE POLICY "cache_service_read" ON cache FOR SELECT USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='cache' AND policyname='cache_service_write') THEN
    CREATE POLICY "cache_service_write" ON cache FOR INSERT WITH CHECK (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='cache' AND policyname='cache_service_update') THEN
    CREATE POLICY "cache_service_update" ON cache FOR UPDATE USING (true);
  END IF;
END $$;

-- ────────────────────────────────────────────────
-- 2. Analyses table (completed analysis results)
-- ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
  id                 uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at         timestamptz DEFAULT now() NOT NULL,

  -- Location
  lat                double precision NOT NULL,
  lng                double precision NOT NULL,
  address            text,
  region_city        text,

  -- Retailer
  retailer_name      text,
  retailer_profile   jsonb,

  -- Scores
  overall_score      double precision,
  recommendation     text,
  score_breakdown    jsonb,
  hotspot_score      double precision,
  demand_score       double precision,
  competition_score  double precision,
  neighborhood_score double precision,

  -- Demographics snapshot
  population         integer,
  median_income      double precision,
  competitor_count   integer
);

CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);

ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='analyses' AND policyname='analyses_public_read') THEN
    CREATE POLICY "analyses_public_read" ON analyses FOR SELECT USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='analyses' AND policyname='analyses_service_write') THEN
    CREATE POLICY "analyses_service_write" ON analyses FOR INSERT WITH CHECK (true);
  END IF;
END $$;
