-- ─────────────────────────────────────────────────────────────
-- Retail Expansion AI — Agent Layer Tables
-- Run AFTER 002_rls.sql in Supabase → SQL Editor → Run
-- ─────────────────────────────────────────────────────────────


-- 1. One row per debate session (per run + store format)
CREATE TABLE IF NOT EXISTS agent_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    store_format  TEXT NOT NULL,
    metrics       JSONB,
    composite_score NUMERIC,
    created_at    TIMESTAMPTZ DEFAULT now()
);


-- 2. Every message from every agent in the debate (full transcript)
CREATE TABLE IF NOT EXISTS agent_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    agent_name  TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);


-- 3. Final verdict from the orchestrator
CREATE TABLE IF NOT EXISTS feasibility_verdicts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    score                   INT,
    recommendation          TEXT,
    confidence              TEXT,
    capture_rate_pct        NUMERIC,
    annual_revenue_estimate NUMERIC,
    summary                 TEXT,
    deciding_factors        JSONB,
    created_at              TIMESTAMPTZ DEFAULT now()
);


-- ── RLS policies (public read, service-role write) ──
ALTER TABLE agent_sessions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_messages       ENABLE ROW LEVEL SECURITY;
ALTER TABLE feasibility_verdicts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public can read agent_sessions"       ON agent_sessions       FOR SELECT USING (true);
CREATE POLICY "public can read agent_messages"       ON agent_messages       FOR SELECT USING (true);
CREATE POLICY "public can read feasibility_verdicts" ON feasibility_verdicts FOR SELECT USING (true);


-- ── Indexes ──
CREATE INDEX IF NOT EXISTS idx_sessions_run    ON agent_sessions(run_id);
CREATE INDEX IF NOT EXISTS idx_messages_sess   ON agent_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_sess   ON feasibility_verdicts(session_id);
