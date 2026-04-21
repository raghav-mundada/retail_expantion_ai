# Atlas — Retail Site Intelligence

A full-stack web application for data-driven retail site selection. Pick a location on a map, and Atlas ingests live data from six external sources — demographics, competitors, parcels, schools, traffic, and neighborhood boundaries — scores every candidate site, and optionally runs an AI bull-vs-bear debate to synthesize a final recommendation.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Running the App](#running-the-app)
- [API Overview](#api-overview)
- [Data Sources](#data-sources)

---

## Features

- **Map-based site selection** — Drop a pin, set a radius, and trigger a full data pipeline for that trade area
- **Auto-scout** — Scores and ranks candidate parcels in the area automatically using store-format-specific metrics (Huff capture, income fit, traffic weighting, etc.)
- **Live data pipeline** — Pulls from US Census ACS, Geoapify, Minneapolis open data, MnDOT traffic, and OpenStreetMap on demand
- **Run caching** — Identical `(lat, lon, radius_km)` queries reuse persisted results, avoiding redundant API calls
- **AI Debate (Oracle)** — Bull and bear LLM agents argue the site; an orchestrator synthesizes a verdict with citations
- **Dashboard** — Interactive maps and cards for demographics, competitors, parcels, schools, and neighborhood context
- **Google sign-in** — Optional auth; signed-in users get a personal run history via `/me/runs`
- **Store formats** — Configurable scoring profiles for different retail formats

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Maps | Leaflet + react-leaflet |
| Charts | Recharts |
| Animations | Framer Motion |
| Icons | Lucide React |
| Backend | Python, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth (Google OAuth) |
| AI Agents | OpenAI `gpt-4o-mini`, LangChain, LangGraph |
| ML | scikit-learn (KMeans clustering) |
| Data | pandas, requests, geopandas (optional) |

---

## Project Structure

```
retail_expantion_ai/
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── App.tsx             # Phase machine: pick → load → dashboard → AI
│   │   ├── lib/
│   │   │   ├── api.ts          # Fetch helpers + types for FastAPI
│   │   │   ├── supabase.ts     # Supabase JS client
│   │   │   └── auth.tsx        # Google OAuth via Supabase
│   │   └── components/
│   │       ├── MapPicker.tsx
│   │       ├── Dashboard.tsx
│   │       ├── ScoutResults.tsx
│   │       ├── AIRecommendation.tsx
│   │       ├── HistoryPanel.tsx
│   │       └── ...
│   ├── vite.config.ts
│   └── package.json
│
├── backend/                    # Python package
│   ├── api/
│   │   ├── main.py             # FastAPI app, CORS, router registration
│   │   ├── deps.py             # JWT auth helpers (optional_user / require_user)
│   │   └── routes/
│   │       ├── analyze.py      # POST /analyze — pipeline + cache
│   │       ├── runs.py         # GET /runs/{id} and data slices
│   │       ├── scout.py        # POST /scout, GET /store-formats
│   │       ├── debate.py       # AI debate start/list/replay
│   │       └── me.py           # GET /me/runs (auth required)
│   ├── pipeline/
│   │   ├── fetch_all.py        # Unified 6-source pipeline
│   │   └── overpass_client.py  # OpenStreetMap Overpass helper
│   ├── ingestion/
│   │   ├── demographics/       # ACS + TIGERweb
│   │   ├── parcels/            # Minneapolis commercial parcels
│   │   └── neighborhoods/      # Neighborhood boundaries
│   ├── scoring/
│   │   ├── metrics.py          # Composite scoring + store format configs
│   │   └── scout.py            # run_scout() — ranks candidate sites
│   ├── agents/
│   │   ├── llm.py              # OpenAI wrapper
│   │   ├── bull.py             # Bull persona
│   │   ├── bear.py             # Bear persona
│   │   ├── orchestrator.py     # Synthesizes verdict
│   │   ├── run_debate.py       # Debate orchestration
│   │   ├── scout.py            # LangGraph autonomous scout agent
│   │   └── K_means.py          # KMeans for candidate clustering
│   └── db/
│       ├── client.py           # Supabase Python client (service role)
│       └── persist_run.py      # Maps pipeline output → Supabase rows
│
└── supabase/
    └── migrations/             # 001–005 ordered SQL migrations
        ├── 001_schema.sql      # Core tables
        ├── 002_rls.sql         # Row-level security
        ├── 003_agents.sql      # Agent sessions + debate verdicts
        ├── 004_tract_centroids.sql
        └── 005_auth.sql        # user_id, store_format on analysis_runs
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- A [Supabase](https://supabase.com) project
- A [Geoapify](https://www.geoapify.com) API key
- An [OpenAI](https://platform.openai.com) API key

### Installation

```bash
# Clone the repo
git clone https://github.com/your-org/retail_expantion_ai.git
cd retail_expantion_ai

# Install frontend deps
cd frontend && npm install && cd ..

# Install backend deps
pip install fastapi uvicorn supabase python-dotenv requests openai pandas \
            scikit-learn numpy langchain langchain-openai langgraph
# Optional (for MnDOT traffic geospatial joins):
pip install geopandas
```

---

## Environment Variables

**Backend** — create `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
GEOAPIFY_API_KEY=your-geoapify-key
OPENAI_API_KEY=your-openai-key
```

**Frontend** — create `frontend/.env.local`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE=http://localhost:8000
```

---

## Database Setup

Run the migrations in order using the Supabase SQL Editor or CLI:

```bash
# Via Supabase CLI (from repo root)
supabase db push

# Or paste each file manually in the Supabase SQL Editor:
# supabase/migrations/001_schema.sql
# supabase/migrations/002_rls.sql
# supabase/migrations/003_agents.sql
# supabase/migrations/004_tract_centroids.sql
# supabase/migrations/005_auth.sql
```

---

## Running the App

**Backend (FastAPI):**

```bash
cd backend
uvicorn backend.api.main:app --reload --port 8000
```

**Frontend (Vite dev server):**

```bash
cd frontend
npm run dev
# Runs on http://localhost:5173
```

Both must run simultaneously. The frontend proxies API requests to `VITE_API_BASE` (defaults to `http://localhost:8000`).

---

## API Overview

| Method | Route | Description |
|---|---|---|
| `POST` | `/analyze` | Run full pipeline for a lat/lon/radius; cached on repeat |
| `GET` | `/runs/{id}` | Fetch a full analysis run |
| `GET` | `/runs/{id}/demographics` | Demographics slice |
| `GET` | `/runs/{id}/competitors` | Competitor slice |
| `GET` | `/runs/{id}/parcels` | Parcel slice |
| `POST` | `/scout` | Score and rank candidate sites |
| `GET` | `/store-formats` | Available store format configs |
| `POST` | `/runs/{id}/debate` | Start or resume AI bull/bear debate |
| `GET` | `/me/runs` | Authenticated user's run history |

---

## Data Sources

| Source | What it provides |
|---|---|
| US Census ACS (5-year) | Income, population, age, household demographics by census tract |
| TIGERweb | Census tract boundaries and centroids |
| Geoapify | Competitor locations, nearby schools, points of interest |
| Minneapolis Open Data | Commercial parcels and assessor data |
| MnDOT AADT | Annual average daily traffic counts (requires geopandas) |
| OpenStreetMap (Overpass) | Supplementary POI and road network data |
