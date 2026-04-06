"""Stage 2 — Content Curation.

LLM-based phase that takes raw collected items and produces a curated,
deduplicated, validated master list with enriched descriptions.
"""

from dataclasses import dataclass
from typing import Optional

from cmbagent.phases.aiweekly.base import AIWeeklyPhaseBase, AIWeeklyPhaseConfig, PhaseContext


@dataclass
class AIWeeklyCurationConfig(AIWeeklyPhaseConfig):
    phase_type: str = "aiweekly_curation"


class AIWeeklyCurationPhase(AIWeeklyPhaseBase):
    config_class = AIWeeklyCurationConfig

    def __init__(self, config=None):
        super().__init__(config or AIWeeklyCurationConfig())

    @property
    def phase_type(self) -> str:
        return "aiweekly_curation"

    @property
    def display_name(self) -> str:
        return "Content Curation"

    @property
    def shared_output_key(self) -> str:
        return "curated_items"

    @property
    def output_filename(self) -> str:
        return "curated.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior AI news editor and fact-checker. Your job is to take a raw list of "
            "collected news items and produce a curated, validated master list. "
            "Remove duplicates, verify dates are within range, ensure each item "
            "is genuine and newsworthy. Group by organization.\n\n"
            "CRITICAL VERIFICATION RULES:\n"
            "1. ZERO HALLUCINATION — Only include items that appear in the raw source data. "
            "Never invent, fabricate, or assume any news item, quote, or fact.\n"
            "2. NO INVENTED PRODUCT NAMES — Every product/model/service name must come directly "
            "from the source data. Do not guess or extrapolate product names.\n"
            "3. DATE VERIFICATION — Every date must be explicitly present in the source entry. "
            "If a date cannot be confirmed from the source, mark it as [DATE UNVERIFIED].\n"
            "4. LINK VERIFICATION — Only include URLs that appear verbatim in the source data. "
            "Never construct or guess URLs.\n"
            "5. NO UNVERIFIED METRICS — Do not include performance numbers, benchmarks, "
            "user counts, revenue figures, or percentage claims unless they appear verbatim "
            "in the source data with attribution.\n"
            "6. NO PERFORMANCE CLAIMS — Remove subjective performance claims like "
            "'breakthrough', 'state-of-the-art', 'best-in-class', 'revolutionary' unless "
            "they are direct quotes from the source with attribution."
        )

    @property
    def specialist_system_prompt(self) -> Optional[str]:
        return (
            "You are a strict fact-checking specialist for AI industry news. "
            "Review the curated item list for:\n"
            "1. Duplicate entries (same release under different titles)\n"
            "2. Date accuracy — every item must have a valid YYYY-MM-DD date that matches source data\n"
            "3. Source credibility — flag any suspicious or unverifiable items\n"
            "4. Organization diversity — ensure broad coverage beyond just "
            "OpenAI/Google/Microsoft\n"
            "5. Relevance — remove items not related to AI/ML/tech\n"
            "6. HALLUCINATION CHECK — Cross-reference every item title, product name, and fact "
            "against the raw source data. Remove any item that cannot be traced back to a source entry.\n"
            "7. INVENTED NAMES — Flag and remove any product/model/tool names that do not appear "
            "verbatim in the source data.\n"
            "8. METRIC VERIFICATION — Remove or mark as [UNVERIFIED] any performance numbers, "
            "benchmarks, or statistics that are not directly quoted from a source.\n"
            "9. PERFORMANCE CLAIMS — Strip subjective superlatives (breakthrough, revolutionary, "
            "state-of-the-art) unless they are direct attributed quotes.\n"
            "Return the COMPLETE improved list, not commentary."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        raw = context.shared_state.get("raw_collection", "(No data collected)")
        cfg = context.shared_state.get("task_config", {})
        date_from = cfg.get("date_from", "")
        date_to = cfg.get("date_to", "")
        topics = ", ".join(cfg.get("topics", []))

        return f"""Curate the following raw news collection into a validated master list.

**Date Range:** {date_from} to {date_to} (INCLUSIVE — reject items outside this range)
**Topics:** {topics}

Rules:
1. Each item appears EXACTLY ONCE — deduplicate by release name + organization + URL
2. Every item must have: title, organization, date (YYYY-MM-DD), source URL, brief summary
3. Remove noise: legal/financial filings, non-AI items, archive/historical content
4. Keep items from diverse organizations — not just top 3 companies
5. Sort by date descending (newest first)

FACT-CHECK RULES (MANDATORY):
6. ONLY include items that exist in the raw collection below — NEVER invent items
7. Product/model names must match the source data EXACTLY — do not rename or guess names
8. Dates must come from the source entry — do not estimate or infer dates
9. URLs must be copied verbatim from the source — do not construct or modify URLs
10. Do NOT add metrics/numbers unless they appear in the source text
11. Remove subjective performance claims ("breakthrough", "state-of-the-art") unless directly quoted
12. EVERY item MUST have a real source URL — REMOVE any item where the source is missing, synthesized, or described as "no single source link" or "Synthesis of multiple"
13. NEVER write "Source: (Synthesis of ...)" or similar — if there is no direct URL, DROP the item entirely

Output format (markdown list):
- **[Title]** | [Organization] | [YYYY-MM-DD]
  [2-3 sentence summary using ONLY facts from the source data]
  Source: [URL]

---

Raw Collection:
{raw}"""
