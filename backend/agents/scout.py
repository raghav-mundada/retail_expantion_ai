"""
backend/agents/scout.py
Autonomous Location Scout — KMeans density search — LangGraph
Usage:
    python backend/agents/scout.py "Find the best location for a Trader Joe's in South Minneapolis"
"""

import json
import sys
from pathlib import Path
from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.tools import (
    geocode_neighborhood,
    fetch_location_data,
    score_parcels,
    expand_radius,
    find_optimal_points,
    _fetched_data,
)


# -- LangChain tool wrappers --------------------------------------------------

@tool
def geocode(neighborhood: str, city: str = "Minneapolis, MN") -> dict:
    """Convert a neighborhood name to latitude/longitude coordinates."""
    return geocode_neighborhood(neighborhood, city)


@tool
def get_optimal_points(
    lat: float,
    lon: float,
    radius_km: float = 10.0,
    n_points: int = 9,
) -> dict:
    """
    Fetch tract demographics once at center.
    Score every tract using weighted sum:
      density = 0.25×population + 0.15×schools + 0.20×competitor_dist + 0.15×low_poverty + 0.20×income + 0.05×traffic
    Run KMeans weighted by density score.
    Returns n_points optimal lat/lon search locations.
    Call this FIRST after geocoding.
    """
    return find_optimal_points(lat, lon, radius_km, n_points)


@tool
def fetch_and_score(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    store_type: str = "grocery",
    store_size_sqft: int = 45000,
    brand_weight: int = 75,
    top_n: int = 5,
    min_acres: float = 0.5,
) -> dict:
    """
    Fetch full pipeline data at a lat/lon and score all retail parcels.
    Call this for each point returned by get_optimal_points.
    Returns top N parcels ranked by Huff gravity score.
    Each parcel includes lat, lon coordinates.
    """
    result = fetch_location_data(lat, lon, radius_km)
    if "data" in result:
        data = result.pop("data")
        _fetched_data["latest"] = data
    else:
        return {"error": result.get("error", "fetch failed"), "top_parcels": []}

    scored = score_parcels(
        _fetched_data["latest"],
        store_type, store_size_sqft, brand_weight, top_n, min_acres,
    )
    scored["fetch_summary"] = result
    return scored


@tool
def get_bigger_radius(current_radius_km: float, reason: str = "") -> dict:
    """Get a suggested larger search radius when current area has too few results."""
    return expand_radius(current_radius_km, reason)


TOOLS = [geocode, get_optimal_points, fetch_and_score, get_bigger_radius]


# -- System prompt ------------------------------------------------------------

SYSTEM_PROMPT = """You are an autonomous retail site selection agent for the Minneapolis metro area.

Given a natural language request, find the best locations to open a retail store.

Your decision process:
1. geocode the requested neighborhood → get center lat/lon

2. get_optimal_points at that center, radius_km=10, n_points=9
   - Fetches ALL tract demographics in 10km radius
   - Scores each tract: 0.25×population + 0.15×schools + 0.20×competitor_dist + 0.15×low_poverty + 0.20×income + 0.05×traffic
   - Runs KMeans weighted by density score
   - Returns 9 points pulled toward high-value customer clusters
   - NOT a grid — every point chosen because the data says customers are there

3. fetch_and_score at each of the 9 returned points (radius_km=5)
   - Fetches parcels + competitors at that location
   - Scores parcels using Huff gravity model
   - Returns top parcels with lat/lon coordinates for each point

4. After all 9 points searched:
   - Collect ALL parcels returned across all points
   - Deduplicate by address — if same address appears multiple times keep highest Huff score
   - Rank all unique parcels by Huff capture probability descending
   - Pick the top 3 unique parcels and write the final report

Store type → brand_weight:
  Target, Costco=90 | Whole Foods, Trader Joe's=80 | Hy-Vee, Cub Foods=70 | Aldi=60 | Pharmacy=75

Store type → store_size_sqft:
  Big box=100000 | Mid grocery (Trader Joe's)=40000 | Small grocery (Aldi)=18000 | Pharmacy=12000

Store type → min_acres:
  Big box=2.0 | Mid grocery=1.0 | Small grocery=0.5 | Pharmacy=0.3

After all 9 points searched write this exact report:

═══════════════════════════════════════════════════════════════
RETAIL SITE SCOUT REPORT
═══════════════════════════════════════════════════════════════
Request      : [original prompt]
Area         : [geocoded display name — neighbourhood only, not full address]
Search method: KMeans density-weighted — 9 points from [tracts] tracts
Weights      : population=0.25, schools=0.15, competitor_dist=0.20, low_poverty=0.15, income=0.20, traffic=0.05
═══════════════════════════════════════════════════════════════

SEARCH POINTS USED
  #1 (lat, lon) density=X — [nearest tract name]
  #2 ...
  #9 ...

TOP 3 RECOMMENDED SITES  (deduplicated, ranked by Huff capture)
─────────────────────────────────────────────────────────────
#1 — [Address]
   Coordinates       : ([lat], [lon])
   Huff Capture      : [X]%
   Est. Weekly Visits: [N]
   Population (1km)  : [N]
   Median Income     : $[N]
   Nearest Competitor: [name] at [X]km
   Parcel Size       : [X] acres

   WHY THIS SITE:
   [2-3 sentences using actual numbers from the data]

#2 — [Address]
   Coordinates       : ([lat], [lon])
   Huff Capture      : [X]%
   Est. Weekly Visits: [N]
   Population (1km)  : [N]
   Median Income     : $[N]
   Nearest Competitor: [name] at [X]km
   Parcel Size       : [X] acres

   WHY THIS SITE:
   [2-3 sentences using actual numbers from the data]

#3 — [Address]
   Coordinates       : ([lat], [lon])
   Huff Capture      : [X]%
   Est. Weekly Visits: [N]
   Population (1km)  : [N]
   Median Income     : $[N]
   Nearest Competitor: [name] at [X]km
   Parcel Size       : [X] acres

   WHY THIS SITE:
   [2-3 sentences using actual numbers from the data]

─────────────────────────────────────────────────────────────
AGENT NOTES
[Observations: how many unique parcels found across 9 points,
 any points with 0 results, data quality caveats]
═══════════════════════════════════════════════════════════════

CRITICAL RULES:
- Never invent numbers. Use only what the tools returned.
- Coordinates must be the actual parcel lat/lon from tool results.
- Huff scores must be real percentages from tool results, not 100%.
- Top 3 must be the 3 highest Huff scores after deduplication."""


# -- State --------------------------------------------------------------------

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# -- Nodes --------------------------------------------------------------------

llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)


def agent_node(state: AgentState) -> AgentState:
    print("  [agent] thinking...")
    return {"messages": [llm.invoke(state["messages"])]}


def log_tools(state: AgentState) -> AgentState:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls"):
        for tc in last.tool_calls:
            print(f"  [tool]  {tc['name']}({json.dumps(tc['args'])})")
    return state


# -- Graph --------------------------------------------------------------------

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("agent",     agent_node)
    g.add_node("log_tools", log_tools)
    g.add_node("tools",     ToolNode(TOOLS))

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {
        "tools": "log_tools",
        END    : END,
    })
    g.add_edge("log_tools", "tools")
    g.add_edge("tools",     "agent")
    return g.compile()


# -- Runner -------------------------------------------------------------------

def run_scout(prompt: str) -> str:
    print(f"\n{'═'*65}")
    print(f"SCOUT AGENT — KMeans density search")
    print(f"Prompt: {prompt}")
    print(f"{'═'*65}\n")

    final = build_graph().invoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    })
    return final["messages"][-1].content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python backend/agents/scout.py "Find best location for Trader Joes in South Minneapolis"')
        sys.exit(1)
    print(run_scout(" ".join(sys.argv[1:])))