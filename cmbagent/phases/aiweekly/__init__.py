"""
AI Weekly Report Phases.

Four-stage pipeline:
  1. Data Collection — Direct tool calls (RSS, APIs, web search)
  2. Content Curation — LLM filters, deduplicates, validates
  3. Report Generation — LLM writes the 4-section report
  4. Quality Review — LLM polishes to publication quality
"""

from cmbagent.phases.aiweekly.collection_phase import AIWeeklyCollectionPhase, AIWeeklyCollectionConfig
from cmbagent.phases.aiweekly.curation_phase import AIWeeklyCurationPhase, AIWeeklyCurationConfig
from cmbagent.phases.aiweekly.generation_phase import AIWeeklyGenerationPhase, AIWeeklyGenerationConfig
from cmbagent.phases.aiweekly.review_phase import AIWeeklyReviewPhase, AIWeeklyReviewConfig
from cmbagent.phases.aiweekly.base import AIWeeklyPhaseBase, AIWeeklyPhaseConfig, AIWeeklyTaskConfig

__all__ = [
    "AIWeeklyCollectionPhase", "AIWeeklyCollectionConfig",
    "AIWeeklyCurationPhase", "AIWeeklyCurationConfig",
    "AIWeeklyGenerationPhase", "AIWeeklyGenerationConfig",
    "AIWeeklyReviewPhase", "AIWeeklyReviewConfig",
    "AIWeeklyPhaseBase", "AIWeeklyPhaseConfig", "AIWeeklyTaskConfig",
]
