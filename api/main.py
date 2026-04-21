"""
FastAPI application entry point.

Main application module that sets up the FastAPI server,
configures CORS, and includes all API routes.
"""

import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import quotes, authors, sources, news
from config import settings
from utils.error_handling import AphoriumError, format_error_response
from logger_config import logger

_stop_news_ingest = threading.Event()


def _news_ingest_worker() -> None:
    """Background loop: RSS + NewsAPI on a fixed interval."""
    from services.news_periodic import run_news_ingestion_cycle

    while True:
        if _stop_news_ingest.wait(settings.news_fetch_interval_seconds):
            break
        try:
            run_news_ingestion_cycle()
        except Exception:
            logger.exception("scheduled news ingest failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start optional news ingest thread; stop on shutdown."""
    thread: Optional[threading.Thread] = None
    if settings.news_periodic_fetch_enabled:
        _stop_news_ingest.clear()
        thread = threading.Thread(
            target=_news_ingest_worker,
            name="aphorium-news-ingest",
            daemon=True,
        )
        thread.start()
    yield
    if thread is not None:
        _stop_news_ingest.set()
        thread.join(timeout=8.0)


# Create FastAPI app with metadata
app = FastAPI(
    title="Aphorium API",
    description=(
        "Search engine for aphorisms and quotes from English and "
        "Russian literature"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware (for frontend access)
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Exception handlers
@app.exception_handler(AphoriumError)
async def aphorium_error_handler(request: Request, exc: AphoriumError):
    """Handle custom Aphorium errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc)
    )

# Include routers
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])
app.include_router(authors.router, prefix="/api/authors", tags=["authors"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(news.router, prefix="/api/news", tags=["news"])


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

