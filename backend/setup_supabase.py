#!/usr/bin/env python3
"""
Run this once to create the `analyses` table in your Supabase project.
Usage:  cd backend && python3 setup_supabase.py
"""
import os, sys, requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL", "").rstrip("/")
service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

if not url or not service_key or "your_" in service_key:
    print("❌  SUPABASE_URL or SUPABASE_SERVICE_KEY is missing in backend/.env")
    print("    → Go to Supabase dashboard → Settings → API → copy Project URL + service_role key")
    sys.exit(1)

print(f"🔌  Connecting to: {url}")

# ── Test connectivity ─────────────────────────────────────────────────────────
test = requests.get(
    f"{url}/rest/v1/",
    headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
    timeout=10,
)
if test.status_code == 401:
    print("❌  API key rejected (401). Your SUPABASE_SERVICE_KEY doesn't match this project URL.")
    print("    → Check Settings → API in your Supabase dashboard for the correct service_role key.")
    sys.exit(1)
print(f"✅  Connected ({test.status_code})")

# ── Create table via SQL API ──────────────────────────────────────────────────
SQL = """
CREATE TABLE IF NOT EXISTS analyses (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at      timestamptz DEFAULT now() NOT NULL,
  lat             double precision NOT NULL,
  lng             double precision NOT NULL,
  address         text,
  region_city     text,
  retailer_name   text,
  retailer_profile jsonb,
  overall_score   double precision,
  recommendation  text,
  score_breakdown jsonb,
  hotspot_score   double precision,
  demand_score    double precision,
  competition_score double precision,
  neighborhood_score double precision,
  population      integer,
  median_income   double precision,
  competitor_count integer
);

CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);

ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='analyses' AND policyname='Allow public read') THEN
    CREATE POLICY "Allow public read" ON analyses FOR SELECT USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='analyses' AND policyname='Allow service write') THEN
    CREATE POLICY "Allow service write" ON analyses FOR INSERT WITH CHECK (true);
  END IF;
END $$;
"""

resp = requests.post(
    f"{url}/rest/v1/rpc/exec_sql",
    headers={
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    },
    json={"query": SQL},
    timeout=30,
)

# Some Supabase plans expose the SQL API differently — try Postgres direct via REST
if resp.status_code not in (200, 201, 204):
    # Alternative: use the pg_dump endpoint
    print(f"⚠️  SQL API returned {resp.status_code} — trying alternative endpoint...")
    resp2 = requests.post(
        f"{url}/rest/v1/rpc/query",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        json={"query": SQL},
        timeout=30,
    )
    if resp2.status_code not in (200, 201, 204):
        print()
        print("⚠️  Could not auto-create table via REST API.")
        print("    → Run this SQL manually in Supabase Dashboard → SQL Editor → New Query:")
        print()
        print("=" * 60)
        print(open(os.path.join(os.path.dirname(__file__), "db/create_analyses_table.sql")).read())
        print("=" * 60)
        sys.exit(0)

print("✅  Table 'analyses' created (or already exists)!")
print()
print("🎉  Supabase is ready. Run a RetailIQ analysis and it will auto-save.")

# ── Quick insert test ─────────────────────────────────────────────────────────
test_row = requests.post(
    f"{url}/rest/v1/analyses",
    headers={
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    },
    json={
        "lat": 44.98, "lng": -93.27,
        "address": "Test — Hennepin County MN",
        "retailer_name": "Setup Test",
        "overall_score": 99.0,
        "recommendation": "Setup Verified",
    },
    timeout=10,
)
if test_row.status_code in (200, 201):
    print("✅  Test row inserted successfully — writes are working!")
else:
    print(f"⚠️  Test insert returned {test_row.status_code}: {test_row.text[:200]}")
    print("    The table may exist but writes are blocked — check RLS policies.")
