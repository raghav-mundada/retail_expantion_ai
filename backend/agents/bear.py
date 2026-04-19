"""
Bear Agent — argues AGAINST opening the store.
Same data as Bull, opposite lens. Surfaces risks the Bull glossed over.
"""

import json
from backend.agents.llm import chat

SYSTEM = """You are the Bear Agent in a retail site selection committee.
Your job: argue persuasively AGAINST opening this store at this location.

Rules:
- Every objection must reference a specific number from the metrics provided.
- Lead with the biggest 2-3 risks, then add supporting concerns.
- Never make up data. If a metric is strong, acknowledge it briefly but pivot
  to a weakness.
- Tone: skeptical, risk-aware, executive. No alarmism — just clear-eyed risk.
- Length: 4-6 short paragraphs maximum.
- End with one bold one-line summary verdict starting with "BEAR CASE:"
"""


def run_bear(metrics: dict) -> str:
    """Generate the bear's argument from the structured metrics object."""
    user = f"""Here is the full metrics scorecard for the candidate location.

Location: ({metrics['center']['lat']}, {metrics['center']['lon']}) within {metrics['center']['radius_km']} km
Store format: {metrics['store_format']}
Composite feasibility score: {metrics['composite_score']}/100

METRICS:
{json.dumps(metrics['metrics'], indent=2)}

Build the case AGAINST opening this store. Be specific with numbers."""

    return chat(SYSTEM, user, temperature=0.75)
