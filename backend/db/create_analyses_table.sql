-- RetailIQ: Create analyses table
-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor → New query)

CREATE TABLE IF NOT EXISTS analyses (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at      timestamptz DEFAULT now() NOT NULL,

  -- Location
  lat             double precision NOT NULL,
  lng             double precision NOT NULL,
  address         text,
  region_city     text,

  -- Retailer
  retailer_name   text,
  retailer_profile jsonb,

  -- Scores
  overall_score       double precision,
  recommendation      text,
  score_breakdown     jsonb,
  hotspot_score       double precision,
  demand_score        double precision,
  competition_score   double precision,
  neighborhood_score  double precision,

  -- Demographics snapshot
  population      integer,
  median_income   double precision,
  competitor_count integer
);

-- Index for fast history queries
CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);

-- Allow anon reads (for frontend history display)
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read" ON analyses
  FOR SELECT USING (true);

CREATE POLICY "Allow service write" ON analyses
  FOR INSERT WITH CHECK (true);
