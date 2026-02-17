import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.tasks import start_scheduler, stop_scheduler

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import routers
from app.routers import health, auth, images
from app.routers.cms import router as cms_router
from app.routers.member import router as member_router
from app.routers.trainer import router as trainer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Moolai Gym API...")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    logger.info("Shutting down Moolai Gym API...")


# Get settings from environment
APP_NAME = os.getenv("APP_NAME", "Moolai Gym API")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

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
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


VALIDATION_MESSAGES = {
    "String should have at least 1 character": "Tidak boleh kosong",
    "Field required": "Wajib diisi",
    "value is not a valid integer": "Harus berupa angka",
    "value is not a valid float": "Harus berupa angka",
    "Value error, value is not a valid email address": "Format email tidak valid",
    "Input should be a valid integer": "Harus berupa angka",
    "Input should be a valid number": "Harus berupa angka",
}


def _translate_validation(error):
    msg = error["msg"]
    translated = VALIDATION_MESSAGES.get(msg)
    if translated:
        return translated
    # Handle pattern: "String should have at least N characters"
    if "should have at least" in msg and "character" in msg:
        return f"Minimal {msg.split('at least ')[1].split(' ')[0]} karakter"
    if "should be greater than" in msg:
        return f"Harus lebih dari {msg.split('greater than ')[1]}"
    if "should be less than" in msg:
        return f"Harus kurang dari {msg.split('less than ')[1]}"
    return msg


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = exc.errors()
    parts = []
    for e in errors:
        field = e["loc"][-1] if e.get("loc") else ""
        translated = _translate_validation(e)
        parts.append(f"{field}: {translated}" if field and field != "__root__" else translated)
    message = "; ".join(parts)
    return JSONResponse(
        status_code=422,
        content={"detail": {"error_code": "VALIDATION_ERROR", "message": message}},
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
app.include_router(images.router)
app.include_router(cms_router)
app.include_router(member_router)
app.include_router(trainer_router)

# Serve uploaded images as static files
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/images")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads/images", StaticFiles(directory=UPLOAD_DIR), name="uploaded-images")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8181, reload=True)
