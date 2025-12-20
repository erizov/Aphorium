"""
FastAPI application entry point.

Main application module that sets up the FastAPI server,
configures CORS, and includes all API routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import quotes, authors, sources
from config import settings
from logger_config import logger

# Create FastAPI app with metadata
app = FastAPI(
    title="Aphorium API",
    description="Search engine for aphorisms and quotes from English and Russian literature",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (for frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for MVP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])
app.include_router(authors.router, prefix="/api/authors", tags=["authors"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])


@app.get("/")
def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Aphorium API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Aphorium API server")
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )

