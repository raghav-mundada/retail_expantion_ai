"""
Bull Agent — argues FOR opening the store.
Reads the metrics scorecard and writes the strongest possible case.
"""

import json
from backend.agents.llm import chat

SYSTEM = """You are the Bull Agent in a retail site selection committee.
Your job: argue persuasively FOR opening this store at this location.

Rules:
- Every claim must reference a specific number from the metrics provided.
- Lead with the strongest 2-3 numbers, then build context.
- Never make up data. If a metric is weak, acknowledge it briefly but pivot
  to a strength.
- Tone: confident, executive, decision-oriented. No fluff.
- Length: 4-6 short paragraphs maximum.
- End with one bold one-line summary verdict starting with "BULL CASE:"
"""


def run_bull(metrics: dict) -> str:
    """Generate the bull's argument from the structured metrics object."""
    user = f"""Here is the full metrics scorecard for the candidate location.

Location: ({metrics['center']['lat']}, {metrics['center']['lon']}) within {metrics['center']['radius_km']} km
Store format: {metrics['store_format']}
Composite feasibility score: {metrics['composite_score']}/100

METRICS:
{json.dumps(metrics['metrics'], indent=2)}

Build the case to OPEN this store. Be specific with numbers."""

    return chat(SYSTEM, user, temperature=0.75)
