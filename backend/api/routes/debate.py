"""
Debate routes — kick off and retrieve agent debates.

  POST /runs/{run_id}/debate            → run a new Bull/Bear/Orchestrator debate
  GET  /runs/{run_id}/debate            → list past debate sessions for the run
  GET  /sessions/{session_id}           → fetch full debate (metrics + transcript + verdict)
  GET  /sessions/{session_id}/messages  → just the agent transcript
  GET  /sessions/{session_id}/verdict   → just the final verdict
"""

import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.client import get_client
from backend.agents.run_debate import run_debate

router = APIRouter()


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
    Triggers a new debate for an existing analysis run.
    Computes metrics → runs Bull → Bear → Orchestrator → persists everything.
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

    return result


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
