"""
Pydantic schemas for the Deepresearch Research Paper wizard endpoints.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class DeepresearchStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Requests
# =============================================================================

class DeepresearchCreateRequest(BaseModel):
    """POST /api/deepresearch/create"""
    task: str = Field("", description="Research description / pitch")
    data_description: Optional[str] = Field(None, description="Optional description of uploaded data")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional model overrides")
    work_dir: Optional[str] = Field(None, description="Base work directory (from frontend config). If not provided, falls back to CMBAGENT_DEFAULT_WORK_DIR")


class DeepresearchExecuteRequest(BaseModel):
    """POST /api/deepresearch/{task_id}/stages/{num}/execute"""
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Per-stage model overrides")


class DeepresearchContentUpdateRequest(BaseModel):
    """PUT /api/deepresearch/{task_id}/stages/{num}/content"""
    content: str = Field(..., description="Updated markdown content")
    field: str = Field("research_idea", description="shared_state key to update (research_idea, methodology, results)")


class DeepresearchRefineRequest(BaseModel):
    """POST /api/deepresearch/{task_id}/stages/{num}/refine"""
    message: str = Field(..., description="User instruction for the LLM")
    content: str = Field(..., description="Current editor content to refine")


# =============================================================================
# Responses
# =============================================================================

class DeepresearchStageResponse(BaseModel):
    """Single stage info in responses."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class DeepresearchCreateResponse(BaseModel):
    """Response for POST /api/deepresearch/create"""
    task_id: str
    work_dir: str
    stages: List[DeepresearchStageResponse]


class DeepresearchStageContentResponse(BaseModel):
    """Response for GET /api/deepresearch/{task_id}/stages/{num}/content"""
    stage_number: int
    stage_name: str
    status: str
    content: Optional[str] = None
    shared_state: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None


class DeepresearchRefineResponse(BaseModel):
    """Response for POST /api/deepresearch/{task_id}/stages/{num}/refine"""
    refined_content: str
    message: str = "Content refined successfully"


class DeepresearchTaskStateResponse(BaseModel):
    """Response for GET /api/deepresearch/{task_id} - full task state for resume."""
    task_id: str
    task: str
    status: str
    work_dir: Optional[str] = None
    created_at: Optional[str] = None
    stages: List[DeepresearchStageResponse]
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    total_cost_usd: Optional[float] = None


class DeepresearchRecentTaskResponse(BaseModel):
    """Single item in GET /api/deepresearch/recent list."""
    task_id: str
    task: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0


class AnalyzeFilesResponse(BaseModel):
    """Response for POST /api/deepresearch/{task_id}/analyze-files"""
    status: str = "started"
    message: str = "File analysis started in background"


class RefineContextRequest(BaseModel):
    """POST /api/deepresearch/{task_id}/refine-context and PUT /api/deepresearch/{task_id}/context"""
    message: str = Field("", description="Refinement instruction (empty for direct save)")
    content: str = Field(..., description="Context content to refine or save")


class RefineContextResponse(BaseModel):
    """Response for POST /api/deepresearch/{task_id}/refine-context"""
    refined_content: str
    message: str = "Context refined successfully"


class UpdateDescriptionRequest(BaseModel):
    """PATCH /api/deepresearch/{task_id}/description"""
    task: Optional[str] = None
    data_description: Optional[str] = None


class AiEditTexRequest(BaseModel):
    """POST /api/deepresearch/{task_id}/ai-edit-tex"""
    tex_path: str = Field(..., description="Absolute path to the .tex file to edit")
    instruction: str = Field(..., description="Natural-language instruction describing the desired changes")


class AiEditTexResponse(BaseModel):
    """Response for POST /api/deepresearch/{task_id}/ai-edit-tex"""
    edited_content: str
    message: str = "LaTeX edited successfully"


class CompileTexRequest(BaseModel):
    """POST /api/deepresearch/{task_id}/compile-tex"""
    tex_path: str = Field(..., description="Absolute path to the .tex file to compile")


class CompileTexResponse(BaseModel):
    """Response for POST /api/deepresearch/{task_id}/compile-tex"""
    pdf_path: Optional[str] = None
    success: bool
    log: str = ""
