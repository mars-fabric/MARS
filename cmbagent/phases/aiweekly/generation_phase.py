"""Stage 3 — Report Generation.

LLM-based phase that takes curated items and produces the full
4-section AI Weekly Report in the required format.
"""

from dataclasses import dataclass
from typing import Optional

from cmbagent.phases.aiweekly.base import AIWeeklyPhaseBase, AIWeeklyPhaseConfig, PhaseContext


@dataclass
class AIWeeklyGenerationConfig(AIWeeklyPhaseConfig):
    phase_type: str = "aiweekly_generation"


class AIWeeklyGenerationPhase(AIWeeklyPhaseBase):
    config_class = AIWeeklyGenerationConfig

    def __init__(self, config=None):
        super().__init__(config or AIWeeklyGenerationConfig())

    @property
    def phase_type(self) -> str:
        return "aiweekly_generation"

    @property
    def display_name(self) -> str:
        return "Report Generation"

    @property
    def shared_output_key(self) -> str:
        return "draft_report"

    @property
    def output_filename(self) -> str:
        return "report_draft.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a professional AI industry report writer producing "
            "publication-ready weekly reports for enterprise distribution. "
            "Write with authority, clarity, and strategic insight.\n\n"
            "STRICT INTEGRITY RULES:\n"
            "- NEVER fabricate, hallucinate, or invent any news item, product name, metric, or fact.\n"
            "- ONLY use information present in the curated data provided. If something is not in the data, do not include it.\n"
            "- Product/model names must match the curated data exactly — no renaming or guessing.\n"
            "- All dates and URLs must come directly from the curated data.\n"
            "- Do NOT add performance metrics, benchmarks, or statistics not present in the source.\n"
            "- Avoid subjective performance claims (breakthrough, revolutionary, state-of-the-art) "
            "unless directly attributed as a quote from the source."
        )

    @property
    def specialist_system_prompt(self) -> Optional[str]:
        return (
            "You are a senior business analyst and fact-checker reviewing an AI Weekly Report draft.\n"
            "1. Ensure Executive Summary captures the week's most significant items\n"
            "2. Key Highlights must be grouped by date sub-headers (### YYYY-MM-DD) with only titles — no full descriptions\n"
            "3. Remove any items whose dates fall outside the stated coverage period\n"
            "4. Check Trends section provides actionable strategic recommendations\n"
            "5. Verify Quick Reference Table matches all items in the report body\n"
            "6. Ensure no duplicate items across sections\n"
            "7. HALLUCINATION CHECK — Remove any item that does not trace back to the curated source data\n"
            "8. PRODUCT NAME CHECK — Flag and remove any product/model names not in the source data\n"
            "9. METRIC CHECK — Remove performance numbers or statistics not present in source data\n"
            "10. CLAIMS CHECK — Strip unattributed superlatives (breakthrough, revolutionary, etc.)\n"
            "Return the COMPLETE improved report, not commentary."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        curated = context.shared_state.get("curated_items", "(No curated data)")
        cfg = context.shared_state.get("task_config", {})
        date_from = cfg.get("date_from", "")
        date_to = cfg.get("date_to", "")
        style = cfg.get("style", "concise")
        topics = ", ".join(cfg.get("topics", []))

        style_title = {"concise": "Concise", "detailed": "Detailed", "technical": "Technical"}.get(style, "Concise")

        return f"""Write a professional AI Weekly Report DRAFT from the curated items below.

**Coverage Period:** {date_from} to {date_to}
**Style:** {style}
**Topics:** {topics}

IMPORTANT: This is a draft. In the Key Highlights section, list ONLY the titles
grouped under date sub-headers for each day in the coverage week. Do NOT write
full descriptions — just the title, organization, and source link for each item.
The final quality review pass will expand them.

Required structure (exactly 4 sections):

# {style_title} AI Weekly Report
Coverage period: {date_from} to {date_to}

## 📋 Executive Summary
3-4 sentence overview of the week's most significant developments.

## 🔥 Key Highlights & Developments
Group items by date (one sub-header per day, newest first).
Under each date, list ONLY the titles — no detailed descriptions.

### YYYY-MM-DD
- **[Title]** — [Organization] [Source link](url)
- **[Title]** — [Organization] [Source link](url)

### YYYY-MM-DD
- **[Title]** — [Organization] [Source link](url)

(repeat for each date that has items within {date_from} to {date_to})

## 💭 Trends & Strategic Implications
3-5 key patterns with evidence and strategic recommendations.

## 📊 Quick Reference Table
| Title | Organization | Date | Link |
|-------|-------------|------|------|

Rules:
- ONLY include items whose dates fall within {date_from} to {date_to}
- Each item appears exactly once in the entire report
- Key Highlights must be grouped by date with only titles (no paragraphs)
- No placeholder text or empty sections
- All links must be real URLs from the curated data

FACT-INTEGRITY RULES (MANDATORY):
- NEVER invent or hallucinate items not present in the curated data below
- Product/model/tool names must match the curated data EXACTLY
- All dates must come from the curated data — do not estimate or fabricate dates
- All URLs must be copied verbatim from the curated data — never construct URLs
- Do NOT add metrics, benchmarks, or performance numbers not in the curated data
- Remove subjective claims ("breakthrough", "state-of-the-art", "revolutionary") unless attributed quotes
- EVERY item MUST have a real source URL from the curated data — skip items with no URL
- NEVER write "Source: (Synthesis of ...)" or "no single source link" — if no URL exists, omit the item

---

Curated Items:
{curated}"""
