"""
Pydantic schemas for the Product Discovery Assistant (PDA) staged wizard endpoints.

7-stage pipeline: 
  1 — Research Summary       (One-Shot (Fast) and Deep Research (planning & control))
  2 — Problem Definition     (direct LLM, background task)
  3 — Opportunity Areas      (direct LLM, background task)
  4 — Solution Archetypes    (direct LLM, background task — needs selected_opportunity)
  5 — Features               (direct LLM, background task — needs selected_archetype)
  6 — Builder Prompts        (direct LLM, background task — needs selected_features)
  7 — Slide Content          (direct LLM, background task)

Stage 0 (client-details) is a direct synchronous endpoint — no session created.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums / status values (mirrors NewsPulse)
# =============================================================================

PDA_STAGE_STATUSES = ("pending", "running", "completed", "failed")


# =============================================================================
# Requests
# =============================================================================

class PdaCreateRequest(BaseModel):
    """POST /api/pda/create — creates task + 7 pending stages."""
    client_name: str = Field("", description="Client / company name")
    industry: str = Field("", description="Primary industry")
    sub_industry: str = Field("", description="Sub-industry")
    client_context: str = Field("", description="Detailed client context paragraph")
    business_function: str = Field("", description="Primary business function")
    discovery_type: str = Field("", description="Discovery type (Problem / Opportunity / ...)")
    process_type: str = Field("new", description="'new' or 'existing'")
    existing_functionality: str = Field("", description="If existing, describe current state")
    problem_keywords: str = Field("", description="Key problem / challenge keywords")
    expected_output: List[str] = Field(default_factory=list, description="Expected deliverables")
    research_mode: str = Field(
        "one_shot",
        description="'one_shot' (fast researcher) or 'planning_and_control' (deep multi-step)",
    )
    work_dir: Optional[str] = Field(None, description="Base work directory override")
    config: Optional[Dict[str, Any]] = Field(None, description="Model / LLM config overrides")


class PdaExecuteRequest(BaseModel):
    """POST /api/pda/{task_id}/stages/{num}/execute"""
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Per-stage LLM overrides")
    # Stage-specific selections passed as input data:
    #   Stage 4 → {"selected_opportunity": <OpportunityArea dict>}
    #   Stage 5 → {"selected_archetype": <SolutionArchetype dict>}
    #   Stage 6 → {"selected_features": [<Feature dict>, ...]}
    input_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Extra context injected into shared_state before running the stage",
    )


class PdaContentUpdateRequest(BaseModel):
    """PUT /api/pda/{task_id}/stages/{num}/content"""
    content: str = Field(..., description="Updated markdown or JSON string content")
    field: str = Field("content", description="shared_state key to update")


class PdaRefineRequest(BaseModel):
    """POST /api/pda/{task_id}/stages/{num}/refine"""
    message: str = Field(..., description="User instruction for AI refinement")
    content: str = Field(..., description="Current editor content to refine")


# =============================================================================
# Responses
# =============================================================================

class PdaStageResponse(BaseModel):
    """Single stage summary inside list responses."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class PdaCreateResponse(BaseModel):
    """Response for POST /api/pda/create"""
    task_id: str
    work_dir: str
    stages: List[PdaStageResponse]


class PdaStageContentResponse(BaseModel):
    """Response for GET /api/pda/{task_id}/stages/{num}/content"""
    stage_number: int
    stage_name: str
    status: str
    content: Optional[str] = None
    shared_state: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None


class PdaRefineResponse(BaseModel):
    """Response for POST /api/pda/{task_id}/stages/{num}/refine"""
    refined_content: str
    message: str = "Content refined successfully"


class PdaTaskStateResponse(BaseModel):
    """Response for GET /api/pda/{task_id}"""
    task_id: str
    task: str
    status: str
    work_dir: Optional[str] = None
    created_at: Optional[str] = None
    stages: List[PdaStageResponse]
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    total_cost_usd: Optional[float] = None
    # Intake metadata for display
    client_name: Optional[str] = None
    industry: Optional[str] = None


class PdaRecentTaskResponse(BaseModel):
    """Single item in GET /api/pda/recent"""
    task_id: str
    task: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    client_name: Optional[str] = None
    industry: Optional[str] = None
