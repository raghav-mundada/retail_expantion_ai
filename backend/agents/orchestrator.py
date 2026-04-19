"""
Orchestrator Agent — reads Bull + Bear arguments and the raw metrics,
then produces the final structured verdict.
"""

import json
from backend.agents.llm import chat_json

SYSTEM = """You are the Orchestrator — the senior partner reviewing both
Bull and Bear arguments for a retail site decision. Your output is the
final, board-ready verdict.

You must return STRICTLY valid JSON with this exact shape:

{
  "score": <int 0-100, your final feasibility score>,
  "recommendation": "<one of: STRONG OPEN, OPEN, CONDITIONAL OPEN, HOLD, DO NOT OPEN>",
  "confidence": "<one of: HIGH, MEDIUM, LOW>",
  "summary": "<2-3 sentence executive summary>",
  "deciding_factors": [
    {"factor": "<short label>", "direction": "positive|negative", "evidence": "<specific number from metrics>"},
    ... (3 to 5 factors total)
  ],
  "key_risks": ["<short risk 1>", "<short risk 2>"],
  "key_strengths": ["<short strength 1>", "<short strength 2>"]
}

Rules:
- Weight Bull and Bear arguments based on the actual metric numbers, not rhetoric.
- Your `score` should be close to the composite_score but adjusted by ±15 points
  based on the qualitative weight of risks vs strengths.
- Be decisive. Do not hedge unless confidence is genuinely LOW.
"""


def run_orchestrator(metrics: dict, bull_argument: str, bear_argument: str) -> dict:
    """Synthesize Bull + Bear into a structured verdict."""
    user = f"""METRICS SCORECARD:
{json.dumps(metrics['metrics'], indent=2)}
Composite score: {metrics['composite_score']}/100
Store format: {metrics['store_format']}

BULL ARGUMENT:
{bull_argument}

BEAR ARGUMENT:
{bear_argument}

Now produce the final verdict JSON."""

    return chat_json(SYSTEM, user)
