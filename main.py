import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import routers
from app.routers import health, auth
from app.routers.cms import router as cms_router
from app.routers.member import router as member_router
from app.routers.trainer import router as trainer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Moolai Gym API...")
    yield
    # Shutdown
    logger.info("Shutting down Moolai Gym API...")


# Get settings from environment
APP_NAME = os.getenv("APP_NAME", "Moolai Gym API")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

app = FastAPI(
    title=APP_NAME,
    description="API untuk Moolai Gym Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to Moolai Gym API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(cms_router)
app.include_router(member_router)
app.include_router(trainer_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8181, reload=True)
