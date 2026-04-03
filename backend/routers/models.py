"""
Model Configuration API — exposes available models and per-workflow defaults.

GET  /api/models/config          → full config (available_models + defaults)
GET  /api/models/available       → list of {value, label} model options
GET  /api/models/defaults/{wf}   → stage defaults for a workflow
POST /api/models/reload          → hot-reload model_config.yaml without restart
"""

from fastapi import APIRouter
from typing import Any, Dict, List

from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/models", tags=["Models"])


@router.get("/config")
async def get_model_config() -> Dict[str, Any]:
    """Return full model configuration: available models + all workflow defaults."""
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_full_config()


@router.get("/available")
async def get_available_models() -> List[Dict[str, str]]:
    """Return the list of available model options for UI dropdowns."""
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_available_models()


@router.get("/defaults/{workflow}")
async def get_workflow_defaults(workflow: str) -> Dict[str, Any]:
    """Return per-stage model defaults for a specific workflow.

    workflow: deepresearch | newspulse | pda | rfp
    """
    from cmbagent.config.model_registry import get_model_registry
    registry = get_model_registry()
    full = registry.get_full_config()
    wf_defaults = full.get("workflow_defaults", {}).get(workflow, {})
    return {"workflow": workflow, "stage_defaults": wf_defaults}


@router.post("/reload")
async def reload_model_config() -> Dict[str, str]:
    """Hot-reload model_config.yaml from disk without restarting the server."""
    from cmbagent.config.model_registry import reload_model_registry
    reload_model_registry()
    logger.info("model_config_reloaded_via_api")
    return {"status": "reloaded"}
