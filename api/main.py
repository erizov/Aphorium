"""
FastAPI application entry point.

Main application module that sets up the FastAPI server,
configures CORS, and includes all API routes.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import quotes, authors, sources
from config import settings
from utils.error_handling import AphoriumError, format_error_response
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

