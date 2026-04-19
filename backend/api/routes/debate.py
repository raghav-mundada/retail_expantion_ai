"""
Debate routes — kick off and retrieve agent debates.

  POST /runs/{run_id}/debate            → run a new Bull/Bear/Orchestrator debate
  GET  /runs/{run_id}/debate            → list past debate sessions for the run
  GET  /sessions/{session_id}           → fetch full debate (metrics + transcript + verdict)
  GET  /sessions/{session_id}/messages  → just the agent transcript
  GET  /sessions/{session_id}/verdict   → just the final verdict
"""

import json
import traceback
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.client import get_client
from backend.agents.run_debate import run_debate
from backend.scoring.metrics import (
    compute_composite,
    COMPOSITE_WEIGHTS,
    FORMULA_DOCS,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: rebuild the full DebateResponse shape from a cached agent_session
# without re-running the LLM agents. Cheap — just DB reads + pure math on the
# already-saved metrics dict.
# ─────────────────────────────────────────────────────────────────────────────

def _reconstruct_debate_from_session(session_row: dict) -> dict:
    db = get_client()
    session_id = session_row["id"]

    msgs = (
        db.table("agent_messages")
        .select("agent_name, content")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
        .data
    ) or []

    by_name = {m["agent_name"]: m["content"] for m in msgs}
    bull_text  = by_name.get("Bull", "")
    bear_text  = by_name.get("Bear", "")
    orch_raw   = by_name.get("Orchestrator", "{}")
    try:
        verdict = json.loads(orch_raw) if isinstance(orch_raw, str) else orch_raw
    except json.JSONDecodeError:
        verdict = {}

    metrics = session_row.get("metrics") or {}

    # Reconstruct the per-dimension breakdown from the saved metrics. This is
    # pure math — no DB or LLM — so we get the same `score_breakdown` shape
    # the frontend expects from a fresh debate.
    try:
        composite = compute_composite(
            demand     = metrics.get("demand", {}),
            competition= metrics.get("competition", {}),
            huff       = metrics.get("huff", {}),
            traffic    = metrics.get("traffic", {}),
            income_fit = metrics.get("income_fit", {}),
        )
        breakdown = composite["contributions"]
        composite_score = composite["total"]
    except Exception:
        # Schema drift on old sessions — fall back to what we have.
        breakdown = []
        composite_score = session_row.get("composite_score") or 0

    return {
        "session_id"     : session_id,
        "run_id"         : session_row["run_id"],
        "store_format"   : session_row["store_format"],
        "metrics"        : metrics,
        "composite_score": composite_score,
        "score_breakdown": breakdown,
        "weights"        : COMPOSITE_WEIGHTS,
        "formulas"       : FORMULA_DOCS,
        "bull"           : bull_text,
        "bear"           : bear_text,
        "verdict"        : verdict,
        "cached"         : True,
        "created_at"     : session_row.get("created_at"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Request body
# ─────────────────────────────────────────────────────────────────────────────

class DebateRequest(BaseModel):
    store_format: str = "Target"   # Target | Walgreens | Whole Foods | Trader Joe's


# ─────────────────────────────────────────────────────────────────────────────
# POST /runs/{run_id}/debate — kick off a new debate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/runs/{run_id}/debate")
def start_debate(run_id: str, body: DebateRequest):
    """
    Triggers a NEW debate for an existing analysis run — always fresh.

    For cache-aware behavior (return existing if available, else run fresh),
    the frontend should hit GET /runs/{run_id}/debate/latest first and only
    fall back to this POST when nothing is cached or the user clicks
    "Re-run analysis".
    """
    db = get_client()

    run = db.table("analysis_runs").select("id").eq("id", run_id).execute().data
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    try:
        result = run_debate(run_id, body.store_format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debate failed: {type(e).__name__}: {e}")

    return {**result, "cached": False}


# ─────────────────────────────────────────────────────────────────────────────
# GET /runs/{run_id}/debate/latest — cached most-recent debate (no LLM cost)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/debate/latest")
def latest_debate(
    run_id: str,
    store_format: str | None = Query(default=None),
):
    """
    Return the most recent cached debate for this run in the same shape as
    POST /runs/{run_id}/debate. 404 only if NO debate has ever been run.

    Resolution order:
      1. Most recent session matching the requested store_format (if given)
      2. Most recent session for this run, any format (graceful fallback —
         older analysis_runs were saved before we tracked store_format on
         the run row, so the frontend's default may not match the format
         the original debate actually used)

    No OpenAI calls. No external APIs. Just two indexed DB reads + a tiny
    `compute_composite` math pass on the already-saved metrics JSON.
    """
    db = get_client()

    sessions = []
    if store_format:
        sessions = (
            db.table("agent_sessions")
            .select("*")
            .eq("run_id", run_id)
            .eq("store_format", store_format)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []

    if not sessions:
        # Fallback — most recent debate for this run regardless of format.
        sessions = (
            db.table("agent_sessions")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []

    if not sessions:
        raise HTTPException(
            status_code=404,
            detail=f"No cached debate for run {run_id}",
        )

    return _reconstruct_debate_from_session(sessions[0])


# ─────────────────────────────────────────────────────────────────────────────
# GET /runs/{run_id}/debate — list past debate sessions for the run
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/debate")
def list_sessions(run_id: str):
    db = get_client()
    sessions = (
        db.table("agent_sessions")
        .select("id, store_format, composite_score, created_at")
        .eq("run_id", run_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return {"run_id": run_id, "sessions": sessions, "count": len(sessions)}


# ─────────────────────────────────────────────────────────────────────────────
# GET /sessions/{session_id} — full debate bundle
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    db = get_client()

    session = db.table("agent_sessions").select("*").eq("id", session_id).execute().data
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    session = session[0]

    messages = (
        db.table("agent_messages")
        .select("agent_name, content, created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
        .data
    )
    verdict = (
        db.table("feasibility_verdicts")
        .select("*")
        .eq("session_id", session_id)
        .execute()
        .data
    )

    return {
        "session" : session,
        "messages": messages,
        "verdict" : verdict[0] if verdict else None,
    }


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str):
    db = get_client()
    msgs = (
        db.table("agent_messages")
        .select("agent_name, content, created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
        .data
    )
    return {"session_id": session_id, "messages": msgs}


@router.get("/sessions/{session_id}/verdict")
def get_verdict(session_id: str):
    db = get_client()
    verdict = (
        db.table("feasibility_verdicts")
        .select("*")
        .eq("session_id", session_id)
        .execute()
        .data
    )
    if not verdict:
        raise HTTPException(status_code=404, detail="No verdict yet for this session")
    return verdict[0]
