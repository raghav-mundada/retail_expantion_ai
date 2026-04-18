"""
backend/agents/scout.py
Autonomous Location Scout with grid search - LangGraph
Usage:
    python backend/agents/scout.py "Find the best location for a Trader Joe's in South Minneapolis"
"""

import json
import sys
from pathlib import Path
from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
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
    grid_search,
    _fetched_data,
)


# -- LangChain tool wrappers --------------------------------------------------

@tool
def geocode(neighborhood: str, city: str = "Minneapolis, MN") -> dict:
    """Convert a neighborhood name to latitude/longitude coordinates."""
    return geocode_neighborhood(neighborhood, city)


@tool
def search_grid(
    center_lat: float,
    center_lon: float,
    radius_km: float = 5.0,
    grid_size: int = 3,
    store_type: str = "grocery",
    store_size_sqft: int = 45000,
    brand_weight: int = 75,
    top_n: int = 5,
    min_acres: float = 0.5,
) -> dict:
    """
    Search a grid_size x grid_size grid of points around the center.
    Each point uses the same radius_km. Merges and deduplicates all results.
    Returns top N unique parcels ranked by Huff gravity score.
    Use this instead of fetch_data + score_sites for better area coverage.
    grid_size=3 searches 9 points ~1km apart (recommended).
    grid_size=2 searches 4 points (faster).
    """
    return grid_search(
        center_lat, center_lon, radius_km, grid_size,
        store_type, store_size_sqft, brand_weight, top_n, min_acres,
    )


@tool
def get_bigger_radius(current_radius_km: float, reason: str = "") -> dict:
    """Get a suggested larger search radius when current area has too few results."""
    return expand_radius(current_radius_km, reason)


TOOLS = [geocode, search_grid, get_bigger_radius]


# -- System prompt ------------------------------------------------------------

SYSTEM_PROMPT = """You are an autonomous retail site selection agent for the Minneapolis metro area.

Given a natural language request, find the best locations to open a retail store.

Your decision process:
1. Call geocode to get the center lat/lon for the requested area
2. Call search_grid with that center, grid_size=3, radius_km=5
   - This searches 9 points across the neighborhood and merges all results
   - Much better coverage than a single center point
3. If top_n results come back with fewer than 3 sites, call get_bigger_radius and retry with larger radius
4. Write the final report using only the real numbers from the data

Store type -> brand_weight:
  Target, Costco=90 | Whole Foods, Trader Joe's=80 | Hy-Vee, Cub Foods=70 | Aldi=60 | Pharmacy=75

Store type -> store_size_sqft:
  Big box (Target, Walmart)=100000 | Mid grocery (Trader Joe's)=40000 | Small grocery (Aldi)=18000 | Pharmacy=12000

min_acres guide:
  Big box=2.0 | Mid grocery=1.0 | Small grocery=0.5 | Pharmacy=0.3

After getting results write this exact report:

═══════════════════════════════════════════════════════════════
RETAIL SITE SCOUT REPORT
═══════════════════════════════════════════════════════════════
Request    : [original prompt]
Area       : [geocoded name]
Grid       : [grid_size]x[grid_size] points, [radius_km]km radius each
Unique sites found: [unique_parcels]
═══════════════════════════════════════════════════════════════

RECOMMENDED SITES
─────────────────────────────────────────────────────────────
#1 — [Address]
   Huff Capture      : [X]%
   Est. Weekly Visits: [N]
   Population (1km)  : [N]
   Median Income     : $[N]
   Nearest Competitor: [name] at [X]km
   Parcel Size       : [X] acres

   WHY THIS SITE:
   [2-3 sentences using the actual numbers]

#2 — [same format]
#3 — [same format]

─────────────────────────────────────────────────────────────
AGENT NOTES
[Observations: grid coverage, data quality, any caveats]
═══════════════════════════════════════════════════════════════

Never invent numbers. Use only what the tools returned."""


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
    print(f"SCOUT AGENT")
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
        print('Usage: python backend/agents/scout.py "Find the best location for a Trader Joes in South Minneapolis"')
        sys.exit(1)
    print(run_scout(" ".join(sys.argv[1:])))