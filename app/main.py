# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import lifespan from db module
from app.db import lifespan

# Import routers from the routers module/package
from app.routers import constraints, policies, reporting, tasks_router # Import tasks_router
from app.core.config import settings # Import settings instance

# Create FastAPI app instance with lifespan management
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan # Add the lifespan context manager here
)

# CORS Configuration (keep as is)
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

# Include routers (keep as is)
app.include_router(constraints.router, prefix=settings.API_V1_STR)
app.include_router(policies.router, prefix=settings.API_V1_STR)
app.include_router(reporting.router, prefix=settings.API_V1_STR)
app.include_router(tasks_router.router, prefix=settings.API_V1_STR)

# Root endpoint (keep as is)
@app.get("/", tags=["Root"], include_in_schema=False)
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}. Navigate to /docs for API documentation."}

# Command line execution:
# uvicorn app.main:app --reload --port 8000