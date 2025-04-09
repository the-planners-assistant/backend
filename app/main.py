# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers from the routers module/package
from app.routers import constraints, policies, reporting, tasks_router # Import tasks_router
from app.core.config import settings # Import settings instance

# Create FastAPI app instance
# Use title from settings
app = FastAPI(title=settings.PROJECT_NAME)

# CORS Configuration
origins = [
    "http://localhost", # Base domain for default dev servers
    "http://localhost:3000", # Example: Default Create React App port
    "http://localhost:5173", # Example: Default Vite port
    "http://127.0.0.1:5173", # Explicit IP often needed
    # Add your frontend's actual origin in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Allow specific origins
    allow_credentials=True,
    allow_methods=["*"], # Allow all standard methods
    allow_headers=["*"], # Allow all headers
)

# Include routers from different modules
# Use prefix from settings for versioning
# Ensure paths in routers don't start with '/' if using prefix
app.include_router(constraints.router, prefix=settings.API_V1_STR)
app.include_router(policies.router, prefix=settings.API_V1_STR)
app.include_router(reporting.router, prefix=settings.API_V1_STR)
app.include_router(tasks_router.router, prefix=settings.API_V1_STR) # Include task status router

# Root endpoint (optional - for health check or basic info)
@app.get("/", tags=["Root"], include_in_schema=False) # Exclude from OpenAPI docs if desired
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}. Navigate to /docs for API documentation."}

# Command line execution (for development):
# uvicorn app.main:app --reload --port 8000