"""
Retail Expansion AI — FastAPI backend entry point

Start the server:
    uvicorn backend.api.main:app --reload

Interactive docs:
    http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.analyze import router as analyze_router
from backend.api.routes.runs import router as runs_router
from backend.api.routes.debate import router as debate_router

app = FastAPI(
    title="Retail Expansion AI",
    description="Location intelligence API — pipeline, storage, and agent debate for retail site selection.",
    version="0.1.0",
)

# ── CORS — allow the React frontend (any localhost port during dev) ──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ─────────────────────────────────────────────────────────
app.include_router(analyze_router, tags=["Pipeline"])
app.include_router(runs_router,    tags=["Data"])
app.include_router(debate_router,  tags=["Agents"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Retail Expansion AI is running"}
