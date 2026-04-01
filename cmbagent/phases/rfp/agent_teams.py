"""
Multi-agent team configurations for RFP phases.

Each RFP stage uses a team of 3 specialized agents that collaborate
sequentially:

  1. **Primary Agent** — Domain expert that generates initial content
  2. **Specialist Agent** — Secondary expert that validates, enriches,
     and adds domain-specific depth
  3. **Reviewer Agent** — Quality reviewer with 13-point checklist

Models are assigned per-stage to optimise for the task complexity:

  - GPT-5.3  for complex synthesis (Architecture Design, Proposal Compilation)
  - GPT-4.1  for detailed analysis (Requirements, Tools, Cloud, Implementation, Execution)
  - GPT-4.1 Mini  for cost-effective specialist validation
  - GPT-4o  for fast, reliable reviewing
"""

from typing import Dict


def _cfg_model() -> str:
    """Return the default model from WorkflowConfig (never hardcoded)."""
    try:
        from cmbagent.config import get_workflow_config
        return get_workflow_config().default_llm_model
    except Exception:
        return "gpt-4o"


# ── Model assignments per phase_type ──────────────────────────────────
# Keys: "primary" (generator), "specialist" (validator), "reviewer" (quality)
#
# All roles default to the model configured in WorkflowConfig so that
# switching providers or deployments only requires a single change.

def _build_phase_models() -> Dict[str, Dict[str, str]]:
    """Build per-phase model map using the configured default model."""
    m = _cfg_model()
    return {
        "rfp_requirements":   {"primary": m, "specialist": m, "reviewer": m},
        "rfp_tools":           {"primary": m, "specialist": m, "reviewer": m},
        "rfp_cloud":           {"primary": m, "specialist": m, "reviewer": m},
        "rfp_implementation": {"primary": m, "specialist": m, "reviewer": m},
        "rfp_architecture":   {"primary": m, "specialist": m, "reviewer": m},
        "rfp_execution":      {"primary": m, "specialist": m, "reviewer": m},
        "rfp_proposal":       {"primary": m, "specialist": m, "reviewer": m},
    }


def get_phase_models(phase_type: str) -> Dict[str, str]:
    """Return ``{"primary": ..., "specialist": ..., "reviewer": ...}``
    model assignments for the given *phase_type*.

    Resolved dynamically from WorkflowConfig so config changes take effect
    without restarting.
    """
    models = _build_phase_models()
    m = _cfg_model()
    return models.get(phase_type, {"primary": m, "specialist": m, "reviewer": m})
