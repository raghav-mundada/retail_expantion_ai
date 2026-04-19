"""
Orchestrates a full debate session for a given run_id and store format.

Flow:
  1. Compute metrics from Supabase data        (scoring engine)
  2. Create agent_session row                  (Supabase)
  3. Run Bull → persist message
  4. Run Bear → persist message
  5. Run Orchestrator → persist message + verdict
  6. Return everything for the API response
"""

import json
from backend.db.client import get_client
from backend.scoring.metrics import compute_all_metrics
from backend.agents.bull import run_bull
from backend.agents.bear import run_bear
from backend.agents.orchestrator import run_orchestrator


def run_debate(run_id: str, store_format: str = "Target") -> dict:
    """Run the full Bull → Bear → Orchestrator pipeline for a run_id."""
    db = get_client()

    metrics_bundle = compute_all_metrics(run_id, store_format)

    session = db.table("agent_sessions").insert({
        "run_id"         : run_id,
        "store_format"   : store_format,
        "metrics"        : metrics_bundle["metrics"],
        "composite_score": metrics_bundle["composite_score"],
    }).execute().data[0]
    session_id = session["id"]

    bull_text = run_bull(metrics_bundle)
    db.table("agent_messages").insert({
        "session_id": session_id,
        "agent_name": "Bull",
        "content"   : bull_text,
    }).execute()

    bear_text = run_bear(metrics_bundle)
    db.table("agent_messages").insert({
        "session_id": session_id,
        "agent_name": "Bear",
        "content"   : bear_text,
    }).execute()

    verdict = run_orchestrator(metrics_bundle, bull_text, bear_text)

    db.table("agent_messages").insert({
        "session_id": session_id,
        "agent_name": "Orchestrator",
        "content"   : json.dumps(verdict, indent=2),
    }).execute()

    db.table("feasibility_verdicts").insert({
        "session_id"             : session_id,
        "score"                  : verdict.get("score"),
        "recommendation"         : verdict.get("recommendation"),
        "confidence"             : verdict.get("confidence"),
        "capture_rate_pct"       : metrics_bundle["metrics"]["huff"]["capture_rate_pct"],
        "annual_revenue_estimate": metrics_bundle["metrics"]["sales"]["annual_revenue_usd"],
        "summary"                : verdict.get("summary"),
        "deciding_factors"       : verdict.get("deciding_factors"),
    }).execute()

    return {
        "session_id"     : session_id,
        "run_id"         : run_id,
        "store_format"   : store_format,
        "metrics"        : metrics_bundle["metrics"],
        "composite_score": metrics_bundle["composite_score"],
        "score_breakdown": metrics_bundle["score_breakdown"],
        "weights"        : metrics_bundle["weights"],
        "formulas"       : metrics_bundle["formulas"],
        "bull"           : bull_text,
        "bear"           : bear_text,
        "verdict"        : verdict,
    }
