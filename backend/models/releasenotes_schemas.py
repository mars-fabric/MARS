"""
Pydantic schemas for the Release Notes pipeline endpoints.

Mirrors the Deepresearch schema pattern: staged execution with
DB-backed shared_state, console streaming, and content editing.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Requests
# =============================================================================

class ReleaseNotesCreateRequest(BaseModel):
    """POST /api/release-notes/create"""
    repo_url: str = Field(..., description="GitHub/GitLab HTTPS URL")
    base_branch: str = Field(..., description="Last release branch (base)")
    head_branch: str = Field(..., description="Current release branch (head)")
    auth_token: Optional[str] = Field(None, description="Personal access token (optional, for private repos)")
    extra_instructions: Optional[str] = Field(None, description="Additional instructions for agents")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional model/config overrides")
    work_dir: Optional[str] = Field(None, description="Base work directory override")


class ReleaseNotesExecuteRequest(BaseModel):
    """POST /api/release-notes/{task_id}/stages/{num}/execute"""
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Per-stage config overrides")


class ReleaseNotesContentUpdateRequest(BaseModel):
    """PUT /api/release-notes/{task_id}/stages/{num}/content"""
    content: str = Field(..., description="Updated markdown content")
    field: str = Field(..., description="shared_state key to update")


class ReleaseNotesRefineRequest(BaseModel):
    """POST /api/release-notes/{task_id}/stages/{num}/refine"""
    message: str = Field(..., description="User instruction for the LLM")
    content: str = Field(..., description="Current editor content to refine")


class ReleaseNotesMigrationRequest(BaseModel):
    """POST /api/release-notes/{task_id}/stages/4/execute — extra fields for migration step"""
    migration_type: str = Field("database", description="Migration type: database | api | infrastructure | full")
    extra_instructions: Optional[str] = Field(None, description="Additional instructions for migration generation")


# =============================================================================
# Responses
# =============================================================================

class ReleaseNotesStageResponse(BaseModel):
    """Single stage info in responses."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ReleaseNotesCreateResponse(BaseModel):
    """Response for POST /api/release-notes/create"""
    task_id: str
    session_id: str
    work_dir: str
    stages: List[ReleaseNotesStageResponse]


class ReleaseNotesStageContentResponse(BaseModel):
    """Response for GET /api/release-notes/{task_id}/stages/{num}/content"""
    stage_number: int
    stage_name: str
    status: str
    content: Optional[str] = None
    shared_state: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None
    documents: Optional[Dict[str, str]] = Field(None, description="Multi-document content keyed by doc_key (for analysis stage)")


class ReleaseNotesRefineResponse(BaseModel):
    """Response for POST /api/release-notes/{task_id}/stages/{num}/refine"""
    refined_content: str
    message: str = "Content refined successfully"


class ReleaseNotesTaskStateResponse(BaseModel):
    """Response for GET /api/release-notes/{task_id} — full task state."""
    task_id: str
    session_id: Optional[str] = None
    repo_url: str
    repo_name: str
    base_branch: str
    head_branch: str
    status: str
    work_dir: Optional[str] = None
    created_at: Optional[str] = None
    stages: List[ReleaseNotesStageResponse]
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    total_cost_usd: Optional[float] = None


class ReleaseNotesRecentTaskResponse(BaseModel):
    """Single item in GET /api/release-notes/recent list."""
    task_id: str
    repo_name: str
    base_branch: str
    head_branch: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0


class ReleaseNotesResumeResponse(BaseModel):
    """Response for POST /api/release-notes/{task_id}/resume"""
    task_id: str
    status: str
    stage_num: Optional[int] = None
    message: str
