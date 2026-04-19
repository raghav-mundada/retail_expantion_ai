"""
RetailIQ FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.billing import router as billing_router
from app.api.scout import router as scout_router
from app.core.config import get_settings

_settings = get_settings()

# Build the allowed-origins list dynamically so the backend works in both
# local dev and production without code changes.
_explicit_origins: list[str] = []
_frontend = _settings.frontend_url.rstrip("/")
if _frontend and _frontend not in ("http://localhost:5173", "http://localhost:3000"):
    _explicit_origins.append(_frontend)

app = FastAPI(
    title="RetailIQ API",
    description="AI-powered superstore site selection through U.S. market digital twins",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # Explicit prod origins (e.g. https://retail-iq.vercel.app)
    allow_origins=_explicit_origins,
    # Regex covers: local dev (any port) + any *.vercel.app preview URL
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://[a-zA-Z0-9-]+(\.vercel\.app)$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(scout_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": "RetailIQ",
        "description": "AI-powered superstore site selection platform",
        "docs": "/docs",
        "api": "/api",
    }
