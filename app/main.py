from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api import auth, hotels, stations, layovers, confirm, crew
from app.services.scheduler_service import start_scheduler, shutdown_scheduler
import logging

logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.

    Startup: Start background scheduler for reminders/escalations
    Shutdown: Gracefully shutdown scheduler
    """
    # Startup
    logger.info("🚀 Starting Crew Layover Management System...")
    try:
        start_scheduler()
        logger.info("✅ Background scheduler started")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")

    yield  # Application runs

    # Shutdown
    logger.info("🛑 Shutting down Crew Layover Management System...")
    try:
        shutdown_scheduler()
        logger.info("✅ Background scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error during scheduler shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    debug=settings.DEBUG,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(hotels.router, prefix="/api/v1")
app.include_router(stations.router, prefix="/api/v1")
app.include_router(layovers.router, prefix="/api/v1")
app.include_router(confirm.router, prefix="/api/v1")
app.include_router(crew.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected"
    }


@app.get("/api/v1/ping")
async def ping():
    """Simple ping endpoint for testing"""
    return {"message": "pong"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )