"""
RetailIQ FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="RetailIQ API",
    description="AI-powered superstore site selection through U.S. market digital twins",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": "RetailIQ",
        "description": "AI-powered superstore site selection platform",
        "docs": "/docs",
        "api": "/api",
    }
