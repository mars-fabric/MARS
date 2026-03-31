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

# ── Model assignments per phase_type ──────────────────────────────────
# Keys: "primary" (generator), "specialist" (validator), "reviewer" (quality)

PHASE_AGENT_MODELS: Dict[str, Dict[str, str]] = {
    "rfp_requirements": {
        "primary": "gpt-4.1",
        "specialist": "gpt-4.1-mini",
        "reviewer": "gpt-4o",
    },
    "rfp_tools": {
        "primary": "gpt-4.1",
        "specialist": "gpt-4.1-mini",
        "reviewer": "gpt-4o",
    },
    "rfp_cloud": {
        "primary": "gpt-4.1",
        "specialist": "gpt-4.1-mini",
        "reviewer": "gpt-4o",
    },
    "rfp_implementation": {
        "primary": "gpt-4.1",
        "specialist": "gpt-4.1-mini",
        "reviewer": "gpt-4o",
    },
    "rfp_architecture": {
        "primary": "gpt-5.3",
        "specialist": "gpt-4.1",
        "reviewer": "gpt-4o",
    },
    "rfp_execution": {
        "primary": "gpt-4.1",
        "specialist": "gpt-4.1-mini",
        "reviewer": "gpt-4o",
    },
    "rfp_proposal": {
        "primary": "gpt-5.3",
        "specialist": "gpt-4.1",
        "reviewer": "gpt-4o",
    },
}

DEFAULT_AGENT_MODELS: Dict[str, str] = {
    "primary": "gpt-4.1",
    "specialist": "gpt-4.1-mini",
    "reviewer": "gpt-4o",
}


def get_phase_models(phase_type: str) -> Dict[str, str]:
    """Return ``{"primary": ..., "specialist": ..., "reviewer": ...}``
    model assignments for the given *phase_type*.
    """
    return PHASE_AGENT_MODELS.get(phase_type, DEFAULT_AGENT_MODELS.copy())
