# app/main.py
import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Logging Configuration ---
from app.core.config import settings, get_log_level # Import settings and helper

logging.basicConfig(
    level=get_log_level(), # Use level from config
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout # Log to standard output
)
logger = logging.getLogger(__name__)

# Make libraries like uvicorn and asyncpg use root logger handlers for consistent output
logging.getLogger("uvicorn.access").handlers = logging.getLogger().handlers
logging.getLogger("uvicorn.error").handlers = logging.getLogger().handlers
logging.getLogger("asyncpg").handlers = logging.getLogger().handlers
# --- End Logging Configuration ---


# Import lifespan from db module
from app.db import lifespan

# Import routers from the routers module/package
from app.routers import constraints, policies, reporting, tasks_router # Import tasks_router

# Create FastAPI app instance with lifespan management
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan # Add the lifespan context manager here
)

# CORS Configuration
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Add production frontend origin here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS middleware added.")

# Include routers
app.include_router(constraints.router, prefix=settings.API_V1_STR)
app.include_router(policies.router, prefix=settings.API_V1_STR)
app.include_router(reporting.router, prefix=settings.API_V1_STR)
app.include_router(tasks_router.router, prefix=settings.API_V1_STR)
logger.info(f"Routers included with prefix: {settings.API_V1_STR}")

# Root endpoint
@app.get("/", tags=["Root"], include_in_schema=False)
async def read_root():
    logger.debug("Root endpoint requested.")
    return {"message": f"Welcome to {settings.PROJECT_NAME}. Navigate to /docs for API documentation."}

logger.info(f"FastAPI application '{settings.PROJECT_NAME}' initialized with log level {settings.LOG_LEVEL}.")

# Command line execution:
# uvicorn app.main:app --reload --port 8000