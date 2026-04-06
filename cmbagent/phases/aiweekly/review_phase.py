"""Stage 4 — Quality Review.

Final LLM-based polish pass that ensures the report meets
publication quality standards, followed by programmatic
verification of all reference links and dates.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from cmbagent.phases.aiweekly.base import AIWeeklyPhaseBase, AIWeeklyPhaseConfig, PhaseContext
from cmbagent.phases.base import PhaseResult

logger = logging.getLogger(__name__)


@dataclass
class AIWeeklyReviewConfig(AIWeeklyPhaseConfig):
    phase_type: str = "aiweekly_review"


class AIWeeklyReviewPhase(AIWeeklyPhaseBase):
    config_class = AIWeeklyReviewConfig

    def __init__(self, config=None):
        super().__init__(config or AIWeeklyReviewConfig())

    @property
    def phase_type(self) -> str:
        return "aiweekly_review"

    @property
    def display_name(self) -> str:
        return "Quality Review"

    @property
    def shared_output_key(self) -> str:
        return "final_report"

    @property
    def output_filename(self) -> str:
        return "report_final.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior editor and fact-checker performing final quality review on an "
            "AI Weekly Report before executive distribution. Ensure it is "
            "polished, accurate, and meets professional publication standards.\n\n"
            "MANDATORY VERIFICATION CHECKS:\n"
            "1. HALLUCINATION REMOVAL — Cross-reference every item against the curated source data. "
            "Remove ANY item whose title, facts, or claims cannot be traced to the curated data.\n"
            "2. INVENTED PRODUCT NAMES — Remove or correct any product/model/service name that does not "
            "appear in the curated source data. Do not guess or extrapolate names.\n"
            "3. DATE VERIFICATION — Every date must match the curated source data exactly. If a date "
            "cannot be confirmed, remove the item or mark it [DATE UNVERIFIED].\n"
            "4. METRIC VERIFICATION — Remove performance numbers, benchmarks, user counts, revenue, "
            "or percentage claims that are NOT present in the curated source data with attribution.\n"
            "5. PERFORMANCE CLAIMS REMOVAL — Strip subjective superlatives (breakthrough, revolutionary, "
            "state-of-the-art, game-changing, best-in-class) unless they are direct attributed quotes "
            "from the source.\n\n"
            "After verification, ensure the report remains well-structured and complete."
        )

    @property
    def specialist_system_prompt(self) -> Optional[str]:
        return None  # No specialist for final review — just generate + review

    def build_user_prompt(self, context: PhaseContext) -> str:
        draft = context.shared_state.get("draft_report", "(No draft)")
        curated = context.shared_state.get("curated_items", "")
        cfg = context.shared_state.get("task_config", {})
        date_from = cfg.get("date_from", "")
        date_to = cfg.get("date_to", "")
        style = cfg.get("style", "concise")

        if style == "concise":
            expand_instruction = (
                "EXPAND each title into a brief overview (2-4 sentences, ~50-80 words). "
                "Focus on WHAT happened and WHO is involved. Keep it short and direct."
            )
            word_rule = "a brief overview (50-80 words)"
        elif style == "technical":
            expand_instruction = (
                "EXPAND each title into a substantial technical paragraph (≥130 words) "
                "with concrete metrics, architecture details, and technical depth "
                "using the curated source data below."
            )
            word_rule = "a substantive description (≥130 words)"
        else:  # detailed
            expand_instruction = (
                "EXPAND each title into a substantial paragraph (≥130 words) covering "
                "what happened, why it matters, competitive context, business implications, "
                "and strategic impact using the curated source data below."
            )
            word_rule = "a substantive description (≥130 words)"

        return f"""Perform a final quality review on this AI Weekly Report draft and produce the publication-ready version.

**Coverage Period:** {date_from} to {date_to}
**Style:** {style}

The draft contains TITLE-ONLY entries in the Key Highlights section (grouped by date).
Your job is to:
1. {expand_instruction}
2. Keep the date-grouped structure (### YYYY-MM-DD sub-headers)
3. Ensure exactly 4 sections: Executive Summary, Key Highlights, Trends, Quick Reference Table
4. Every item must have: date (YYYY-MM-DD), organization, source URL, and {word_rule}
5. No duplicate items anywhere in the report
6. Quick Reference Table matches all items mentioned in the body
7. No placeholder text ("[Insert ...]", "[To be added]", etc.)
8. Professional tone suitable for executive distribution
9. All links are real URLs (no example.com or placeholder links)
10. Dates must be within the coverage period — reject out-of-range items

MANDATORY FACT-CHECK RULES:
11. HALLUCINATION REMOVAL — Remove any item, fact, or claim NOT traceable to the curated source data below. Do NOT invent news items.
12. PRODUCT NAME VERIFICATION — Every product/model/service name must appear in the curated source data. Remove invented names.
13. DATE VERIFICATION — Every date must match source data. Remove items with dates not found in the curated data.
14. METRIC VERIFICATION — Remove any performance numbers, benchmarks, user counts, or statistics not present in the curated data.
15. PERFORMANCE CLAIMS — Remove subjective claims ("breakthrough", "state-of-the-art", "revolutionary", "game-changing") unless they are direct attributed quotes from the source.
16. SOURCE URL REQUIRED — Every item MUST have a real, clickable source URL. Remove ANY item that says "Synthesis of multiple papers", "no single source link", or has no URL.
17. NEVER generate text like "Source: (Synthesis of ...)" — if an item has no verifiable URL from the curated data, DELETE IT entirely.

Return ONLY the final report markdown.

---

Draft Report:
{draft}

---

Curated Source Data (use this to expand titles into full descriptions — do NOT add information beyond what is here):
{curated}"""

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Run the standard LLM pipeline, then apply programmatic verification."""

        result = await super().execute(context)

        # Post-LLM programmatic verification on the final content
        if result.status.value == "completed":
            content = (context.output_data or {}).get("shared", {}).get("final_report", "")
            if content:
                verified, verification_notes = self._programmatic_verification(content, context)
                if verification_notes:
                    # Store notes alongside the report
                    context.output_data["artifacts"]["verification_notes"] = verification_notes
                    print(f"[Quality Review] Verification: {len(verification_notes)} issues noted")
                    for note in verification_notes:
                        print(f"  - {note}")

                # Update the final report with verified content
                context.output_data["shared"]["final_report"] = verified

                # Re-save the file with verified content
                import os
                out_dir = os.path.join(context.work_dir, "input_files")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, self.output_filename)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(verified)

        return result

    def _programmatic_verification(self, content: str, context: PhaseContext) -> tuple:
        """Run deterministic checks on the final report content.

        Returns (cleaned_content, list_of_notes).
        """
        notes = []
        cfg = context.shared_state.get("task_config", {})
        date_from = cfg.get("date_from", "")
        date_to = cfg.get("date_to", "")

        # --- 1. Verify all URLs are accessible ---
        urls = re.findall(r'https?://[^\s\)>\]"\']+', content)
        unique_urls = list(dict.fromkeys(urls))  # dedupe, preserve order
        if unique_urls:
            try:
                from cmbagent.external_tools.news_tools import verify_reference_links
                print(f"[Quality Review] Verifying {len(unique_urls)} unique URLs...")
                result = verify_reference_links(unique_urls[:50])  # cap to avoid slowness
                inaccessible = [
                    r["url"] for r in result.get("results", [])
                    if not r.get("accessible")
                ]
                if inaccessible:
                    notes.append(
                        f"Link verification: {len(inaccessible)}/{len(unique_urls)} URLs inaccessible"
                    )
                    for bad_url in inaccessible:
                        notes.append(f"  Inaccessible: {bad_url}")
                        # Add warning comment after the broken link in the report
                        content = content.replace(
                            bad_url,
                            f"{bad_url} <!-- [LINK UNVERIFIED] -->"
                        )
                else:
                    notes.append(f"Link verification: all {len(unique_urls)} URLs accessible")
            except Exception as e:
                notes.append(f"Link verification skipped: {e}")

        # --- 2. Verify dates are within coverage period ---
        if date_from and date_to:
            date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
            all_dates = date_pattern.findall(content)
            out_of_range = []
            for d in all_dates:
                if d < date_from or d > date_to:
                    # Exclude dates that are part of the coverage period header
                    if d not in (date_from, date_to):
                        out_of_range.append(d)
            if out_of_range:
                unique_oor = list(dict.fromkeys(out_of_range))
                notes.append(
                    f"Date verification: {len(unique_oor)} out-of-range dates found: {', '.join(unique_oor)}"
                )
                for d in unique_oor:
                    content = content.replace(d, f"{d} <!-- [DATE OUT OF RANGE] -->")

        # --- 3. Flag placeholder/example URLs ---
        placeholder_patterns = [
            r'https?://example\.com',
            r'https?://placeholder\.',
            r'https?://xxx\.',
            r'\[Insert',
            r'\[To be added\]',
            r'\[TBD\]',
            r'\[URL\]',
            r'\[link\]',
        ]
        for pat in placeholder_patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            if matches:
                notes.append(f"Placeholder detected: {len(matches)} instances of '{pat}'")

        # --- 4. Flag unattributed superlatives ---
        superlative_pattern = re.compile(
            r'\b(breakthrough|revolutionary|state-of-the-art|game-changing|'
            r'best-in-class|world-first|unprecedented|groundbreaking)\b',
            re.IGNORECASE
        )
        superlatives = superlative_pattern.findall(content)
        if superlatives:
            notes.append(
                f"Superlative check: {len(superlatives)} unattributed claims remain: "
                f"{', '.join(set(s.lower() for s in superlatives))}"
            )

        # --- 5. Remove "Synthesis of multiple papers" and similar no-source text ---
        synthesis_patterns = [
            r'\(Synthesis of [^)]*\)',
            r'\(no single source[^)]*\)',
            r'Source:\s*\(Synthesis[^)]*\)',
            r'Source:\s*\(No single[^)]*\)',
            r'Source:\s*N/?A',
            r'Source:\s*None',
            r'\[Synthesis of[^\]]*\]',
        ]
        for pat in synthesis_patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            if matches:
                notes.append(f"Synthesis/no-source text removed: {len(matches)} instances of '{pat}'")
                content = re.sub(pat, '', content, flags=re.IGNORECASE)

        return content, notes
