# app/models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Any # Import Any for task result

# --- Input Models ---

class LocationInput(BaseModel):
    lat: float
    lon: float

class ReportInput(LocationInput):
    proposal_text: Optional[str] = Field(default=None, description="Description of the proposed development")

# --- Data/Info Models ---

class ConstraintInfo(BaseModel):
    id: str
    name: str
    type: str = Field(description="e.g., 'Statutory', 'Local Policy'")
    explanation_available: bool = False

class PolicyInfo(BaseModel):
    id: str
    description: str

class ReportConstraintAnalysis(BaseModel):
    id: str
    name: str
    status: str = Field(description="e.g., 'Present', 'Not Present', 'Potential Conflict'")
    explanation_available: bool = False

class ReportPolicyAnalysis(BaseModel):
    id: str
    relevance_score: float
    reasoning: str = Field(description="Why this policy is relevant")

# --- Response Models ---

class ConstraintsResponse(BaseModel):
    location: LocationInput
    constraints: List[ConstraintInfo]

class PoliciesResponse(BaseModel):
    location: LocationInput
    policies: List[PolicyInfo]

class ReportData(BaseModel):
    request: ReportInput
    proposal_summary: str
    constraints_analysis: List[ReportConstraintAnalysis]
    ai_explanation: str
    relevant_policies: List[ReportPolicyAnalysis]

# Response model when triggering a background task
class AsyncTaskResponse(BaseModel):
    task_id: str
    status: str = "PENDING"

# Response model for checking task status
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str # Celery states: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
    result: Optional[Any] = None # Store result (can be dict matching ReportData or other)
    error: Optional[str] = None # Store error message if failed

# Add other schemas as needed, e.g., for explanations, scenarios etc.