"""
Model Registry — Single source of truth for LLM model configuration.

Loads model_config.yaml located in the same directory.
Environment variables override YAML values at runtime.

Usage:
    from cmbagent.config.model_registry import get_model_registry

    registry = get_model_registry()
    models   = registry.get_available_models()      # for UI dropdowns
    defaults = registry.get_stage_defaults("deepresearch", 1)  # for stage helpers
    model    = registry.get_default_model("researcher_model")  # single role

Hot-reload (without restart):
    from cmbagent.config.model_registry import reload_model_registry
    reload_model_registry()
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "model_config.yaml"

# Env var → global_defaults key mapping
_ENV_OVERRIDE_MAP: Dict[str, str] = {
    "default_model":       "CMBAGENT_DEFAULT_MODEL",
    "planner_model":       "CMBAGENT_PLANNER_MODEL",
    "plan_reviewer_model": "CMBAGENT_PLAN_REVIEWER_MODEL",
    "researcher_model":    "CMBAGENT_RESEARCHER_MODEL",
    "engineer_model":      "CMBAGENT_ENGINEER_MODEL",
    "orchestration_model": "CMBAGENT_ORCHESTRATION_MODEL",
    "formatter_model":     "CMBAGENT_FORMATTER_MODEL",
    "idea_maker_model":    "CMBAGENT_IDEA_MAKER_MODEL",
    "idea_hater_model":    "CMBAGENT_IDEA_HATER_MODEL",
}

# Built-in emergency fallbacks — used when YAML is missing / unreadable
_BUILTIN_FALLBACKS: Dict[str, Any] = {
    "available_models": [
        {"value": "gpt-4.1-2025-04-14", "label": "GPT-4.1"},
        {"value": "gpt-4o",             "label": "GPT-4o"},
        {"value": "o3-mini-2025-01-31", "label": "o3-mini"},
        {"value": "gemini-2.5-flash",   "label": "Gemini 2.5 Flash"},
    ],
    "global_defaults": {
        "default_model":       "gpt-4o",
        "planner_model":       "gpt-4o",
        "plan_reviewer_model": "o3-mini",
        "researcher_model":    "gpt-4.1-2025-04-14",
        "engineer_model":      "gpt-4.1-2025-04-14",
        "orchestration_model": "gpt-4.1-2025-04-14",
        "formatter_model":     "o3-mini",
        "idea_maker_model":    "gpt-4o",
        "idea_hater_model":    "o3-mini",
    },
    "workflow_defaults": {},
}


class ModelRegistry:
    """Loaded + env-overridden model configuration registry."""

    def __init__(self, raw_config: Dict[str, Any]) -> None:
        self._available_models: List[Dict[str, str]] = list(
            raw_config.get("available_models", _BUILTIN_FALLBACKS["available_models"])
        )
        self._global_defaults: Dict[str, str] = dict(
            raw_config.get("global_defaults", _BUILTIN_FALLBACKS["global_defaults"])
        )
        self._workflow_defaults: Dict[str, Dict] = dict(
            raw_config.get("workflow_defaults", {})
        )
        self._apply_env_overrides()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_available_models(self) -> List[Dict[str, str]]:
        """Return list of {value, label} model options for UI dropdowns."""
        return list(self._available_models)

    def get_default_model(self, role: str = "default_model") -> str:
        """Return the global default model for a specific role.

        Falls back to global_defaults.default_model, then 'gpt-4o'.
        """
        return self._global_defaults.get(
            role,
            self._global_defaults.get("default_model", "gpt-4o"),
        )

    def get_stage_defaults(self, workflow: str, stage_num: int) -> Dict[str, Any]:
        """Return merged model defaults for *workflow* + *stage_num*.

        Merge order (lowest → highest priority):
          1. workflow "default" section (if present)
          2. workflow stage-specific section (e.g. "1", "2", …)
          3. env-var overrides (for recognised role keys)

        The caller should then layer user-supplied config_overrides on top:
            cfg = {**registry.get_stage_defaults(wf, n), **config_overrides}
        """
        wf_config = self._workflow_defaults.get(workflow, {})
        result: Dict[str, Any] = {}

        # Merge workflow-level "default" section first
        if "default" in wf_config:
            result.update(wf_config["default"])

        # Merge stage-specific section (overrides "default")
        stage_key = str(stage_num)
        if stage_key in wf_config:
            result.update(wf_config[stage_key])

        # Apply env-var overrides for known role keys that are already present
        for role, env_var in _ENV_OVERRIDE_MAP.items():
            val = os.getenv(env_var)
            if val and role in result:
                result[role] = val

        return result

    def get_full_config(self) -> Dict[str, Any]:
        """Serialize full config for the /api/models/config API endpoint."""
        workflow_serialized: Dict[str, Dict] = {}
        for wf_name, stages in self._workflow_defaults.items():
            wf_entry: Dict[str, Dict] = {}
            for stage_key, stage_cfg in stages.items():
                resolved = dict(stage_cfg)
                for role, env_var in _ENV_OVERRIDE_MAP.items():
                    val = os.getenv(env_var)
                    if val and role in resolved:
                        resolved[role] = val
                wf_entry[str(stage_key)] = resolved
            workflow_serialized[wf_name] = wf_entry

        return {
            "available_models": self._available_models,
            "global_defaults":  self._global_defaults,
            "workflow_defaults": workflow_serialized,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to global_defaults in-place."""
        for role, env_var in _ENV_OVERRIDE_MAP.items():
            val = os.getenv(env_var)
            if val:
                self._global_defaults[role] = val


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Return the singleton ModelRegistry, loading from YAML on first call."""
    global _registry
    if _registry is not None:
        return _registry

    try:
        import yaml  # PyYAML is already a transitive dependency via cmbagent

        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        _registry = ModelRegistry(raw)
        logger.info("model_registry_loaded path=%s", _CONFIG_PATH)
    except FileNotFoundError:
        logger.warning(
            "model_config.yaml not found at %s — using built-in fallbacks", _CONFIG_PATH
        )
        _registry = ModelRegistry(_BUILTIN_FALLBACKS)
    except Exception as exc:  # noqa: BLE001
        logger.error("model_registry_load_failed error=%s", exc)
        _registry = ModelRegistry(_BUILTIN_FALLBACKS)

    return _registry


def reload_model_registry() -> ModelRegistry:
    """Force-reload registry from disk (useful for hot config reload)."""
    global _registry
    _registry = None
    logger.info("model_registry_reloading")
    return get_model_registry()
