# app/models/schemas.py
from pydantic import BaseModel, Field, TypeAdapter
from typing import List, Optional, Any, Dict

# --- Input Models ---
class LocationInput(BaseModel): lat: float; lon: float
class ReportInput(BaseModel):
    lat: float
    lon: float
    # Revert to Optional - allows None input, task handles conversion to "" for prompt
    proposal_text: Optional[str] = Field(default=None, description="Description of the proposed development")

# --- Data/Info Models ---
class ConstraintInfo(BaseModel): id: str; name: str; type: str; explanation_available: bool
class PolicyInfo(BaseModel): id: str; description: str

# --- Response Models ---
class ConstraintsResponse(BaseModel): location: LocationInput; constraints: List[ConstraintInfo]
class PoliciesResponse(BaseModel): location: LocationInput; policies: List[PolicyInfo]

# --- Internal Task Input Model ---
class ReportTaskInput(BaseModel):
    request: ReportInput
    formatted_address: Optional[str] = None
    ranked_constraints: List[ConstraintInfo]
    ranked_policies: List[PolicyInfo]
    aerial_photo_uri: Optional[str] = None
    street_view_photo_uri: Optional[str] = None
    # Mime types can remain removed

# --- Reporting Output Models ---
class ReportConstraintAnalysis(BaseModel): id: str; name: str; status: str; explanation_available: bool
class ReportPolicyAnalysis(BaseModel): id: str; relevance_score: float; reasoning: str

# ReportData is now the target for manual validation inside the task
class ReportData(BaseModel):
    request: ReportInput
    proposal_summary: str
    constraints_analysis: List[ReportConstraintAnalysis]
    relevant_policies: List[ReportPolicyAnalysis]
    ai_explanation: str

# --- LLMReportOutputSchema REMOVED ---

# --- Task Status Models ---
class AsyncTaskResponse(BaseModel): task_id: str; status: str = "PENDING"
class TaskStatusResponse(BaseModel): task_id: str; status: str; result: Optional[ReportData] = None; error: Optional[str] = None

# --- Type Adapters REMOVED (now validating full ReportData) ---
# ConstraintsAnalysisList = TypeAdapter(List[ReportConstraintAnalysis])
# PoliciesAnalysisList = TypeAdapter(List[ReportPolicyAnalysis])