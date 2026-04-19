"""
RetailIQ FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.billing import router as billing_router

app = FastAPI(
    title="RetailIQ API",
    description="AI-powered superstore site selection through U.S. market digital twins",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # dev origins matched via regex below (any Vite port)
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(billing_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": "RetailIQ",
        "description": "AI-powered superstore site selection platform",
        "docs": "/docs",
        "api": "/api",
    }
