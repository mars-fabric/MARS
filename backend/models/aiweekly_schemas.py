"""Pydantic schemas for AI AIWeekly Report endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AIWeeklyCreateRequest(BaseModel):
    topics: List[str] = ["llm", "cv"]
    sources: List[str] = [
        "github", "press-releases", "company-announcements",
        "major-releases", "curated-ai-websites",
    ]
    date_from: str
    date_to: str
    style: str = "concise"
    config: Optional[Dict[str, Any]] = None
    work_dir: Optional[str] = None


class AIWeeklyCreateResponse(BaseModel):
    task_id: str
    work_dir: str
    stages: List[Dict[str, Any]]


class AIWeeklyExecuteRequest(BaseModel):
    config_overrides: Optional[Dict[str, Any]] = None


class AIWeeklyStageResponse(BaseModel):
    stage_number: int
    stage_name: str
    status: str
    output_preview: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class AIWeeklyStageContentResponse(BaseModel):
    stage_number: int
    stage_name: str
    content: str
    field: str


class AIWeeklyContentUpdateRequest(BaseModel):
    content: str
    field: str


class AIWeeklyRefineRequest(BaseModel):
    message: str
    content: str


class AIWeeklyRefineResponse(BaseModel):
    refined_content: str
    message: str


class AIWeeklyTaskStateResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    stages: List[AIWeeklyStageResponse]
    total_cost: Optional[Dict[str, Any]] = None


class AIWeeklyRecentTaskResponse(BaseModel):
    """Single item in GET /api/aiweekly/recent list."""
    task_id: str
    task: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
