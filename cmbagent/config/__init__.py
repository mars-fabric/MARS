"""
Configuration management for CMBAgent.

This module provides configuration dataclasses for:
- Workflow execution parameters
- Agent configuration
"""

from cmbagent.config.workflow_config import (
    WorkflowConfig,
    get_workflow_config,
    set_workflow_config,
    reset_workflow_config,
)
from cmbagent.config.model_registry import (
    ModelRegistry,
    get_model_registry,
    reload_model_registry,
)

__all__ = [
    "WorkflowConfig",
    "get_workflow_config",
    "set_workflow_config",
    "reset_workflow_config",
    "ModelRegistry",
    "get_model_registry",
    "reload_model_registry",
]
