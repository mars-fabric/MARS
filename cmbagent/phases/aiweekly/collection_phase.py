"""Stage 1 — Data Collection.

Calls news_tools directly (no LLM) to gather raw items from all
configured sources. Deduplicates and date-filters before output.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus

logger = logging.getLogger(__name__)

# Priority companies: always get extra web-search coverage
_PRIORITY_COMPANIES = [
    # AI / ML / Foundation Models
    "openai", "google", "deepmind", "microsoft", "anthropic",
    "meta", "amazon", "huggingface",
    # Hardware & Compute
    "nvidia", "intel", "amd", "apple",
    # Robotics
    "bostondynamics",
    # Quantum
    "google_quantum", "ibm", "quantinuum",
    # Cloud & Enterprise AI
    "oracle",
    # Other tech
    "samsung", "salesforce",
]


@dataclass
class AIWeeklyCollectionConfig(PhaseConfig):
    phase_type: str = "aiweekly_collection"


class AIWeeklyCollectionPhase(Phase):
    """Non-LLM phase that runs all data collection tools."""

    config_class = AIWeeklyCollectionConfig

    def __init__(self, config=None):
        super().__init__(config or AIWeeklyCollectionConfig())

    @property
    def phase_type(self) -> str:
        return "aiweekly_collection"

    @property
    def display_name(self) -> str:
        return "Data Collection"

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.external_tools.news_tools import (
            announcements_noauth,
            curated_ai_sources_search,
            newsapi_search,
            gnews_search,
            multi_engine_web_search,
            scrape_official_news_pages,
        )

        self._status = PhaseStatus.RUNNING
        start = time.time()

        try:
            cfg = context.shared_state.get("task_config", {})
            date_from = cfg.get("date_from", "")
            date_to = cfg.get("date_to", "")
            sources = cfg.get("sources", [])

            all_items: List[Dict] = []
            seen_keys: set = set()
            errors: List[str] = []

            def _merge(items: List[Dict], source_cap: int = 0):
                """Merge items into all_items. If source_cap > 0, only add up to that many."""
                added = 0
                for item in items:
                    key = (
                        (item.get("url") or "").strip().lower(),
                        (item.get("title") or "").strip().lower()[:80],
                    )
                    if key not in seen_keys and key[0]:
                        seen_keys.add(key)
                        all_items.append(item)
                        added += 1
                        if source_cap and added >= source_cap:
                            break

            def _safe(fn, label, source_cap: int = 0, **kwargs):
                try:
                    result = fn(**kwargs)
                    items = result.get("items") or result.get("articles") or []
                    print(f"[Data Collection] {label}: {len(items)} items")
                    _merge(items, source_cap=source_cap)
                except Exception as e:
                    errors.append(f"{label}: {e}")
                    print(f"[Data Collection] {label}: ERROR {e}")

            # Step A: Broad official news page sweep
            print(f"[Data Collection] Starting collection for {date_from} to {date_to}")
            _safe(announcements_noauth, "Broad official sweep",
                  query="", company="", from_date=date_from, to_date=date_to, limit=300)

            # Step B: Per-company official news page scraping (direct + web-search)
            print("[Data Collection] Scraping official company news pages...")
            for company in _PRIORITY_COMPANIES:
                _safe(scrape_official_news_pages, f"Official/{company}",
                      company=company, from_date=date_from, to_date=date_to, limit=15)

            # Step C: Log first-party coverage before adding secondary sources
            primary_sources = set(_PRIORITY_COMPANIES)
            primary_count = sum(
                1 for item in all_items
                if (item.get("source") or "").lower().strip() in primary_sources
            )
            print(f"[Data Collection] First-party (official) items so far: {primary_count}/{len(all_items)}")

            # Step D: Curated AI sources (capped to avoid media-aggregator dominance)
            _safe(curated_ai_sources_search, "Curated AI sources",
                  query=f"AI news {date_from} to {date_to}", limit=40,
                  from_date=date_from, to_date=date_to)

            # Step E: NewsAPI (if key available)
            if "press-releases" in sources or "company-announcements" in sources:
                _safe(newsapi_search, "NewsAPI",
                      query="artificial intelligence OR machine learning",
                      from_date=date_from, to_date=date_to, page_size=100)

            # Step F: GNews (if key available)
            _safe(gnews_search, "GNews",
                  query="artificial intelligence OR machine learning",
                  from_date=date_from, to_date=date_to, max_results=100)

            # Step G: Targeted web search for priority companies with zero/few results
            companies_found: Dict[str, int] = {}
            for item in all_items:
                src = (item.get("source") or "").lower().strip()
                companies_found[src] = companies_found.get(src, 0) + 1

            for company in _PRIORITY_COMPANIES:
                if companies_found.get(company, 0) < 2:
                    # Try multiple query variants for better coverage
                    for query_variant in [
                        f"{company} AI product launch announcement",
                        f"{company} artificial intelligence release update",
                    ]:
                        _safe(multi_engine_web_search, f"Web/{company}",
                              query=query_variant,
                              max_results=5, from_date=date_from, to_date=date_to)

            # Step I: Log source distribution for debugging
            source_dist: Dict[str, int] = {}
            for item in all_items:
                src = (item.get("source") or "unknown").lower()
                source_dist[src] = source_dist.get(src, 0) + 1
            sorted_sources = sorted(source_dist.items(), key=lambda x: -x[1])
            print(f"[Data Collection] Source distribution:")
            for src, count in sorted_sources[:20]:
                print(f"  {src}: {count} items")

            print(f"[Data Collection] Total: {len(all_items)} unique items ({len(errors)} errors)")

            # Build output as structured JSON
            collection_data = {
                "date_from": date_from,
                "date_to": date_to,
                "total_items": len(all_items),
                "items": all_items,
                "errors": errors,
            }

            # Save raw collection to file
            out_dir = os.path.join(context.work_dir, "input_files")
            os.makedirs(out_dir, exist_ok=True)
            json_path = os.path.join(out_dir, "collection.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(collection_data, f, indent=2, default=str)

            # Also produce a markdown summary for the shared state
            summary_lines = [
                f"# Data Collection Summary",
                f"**Date Range:** {date_from} to {date_to}",
                f"**Total Items:** {len(all_items)}",
                f"**Errors:** {len(errors)}",
                "",
            ]
            for item in all_items:
                title = item.get("title", "Untitled")
                url = item.get("url", "")
                source = item.get("source", "unknown")
                pub = (item.get("published_at") or "")[:10]
                desc = (item.get("summary") or "")[:200]
                summary_lines.append(f"- **{title}** | {source} | {pub}")
                if desc:
                    summary_lines.append(f"  {desc}")
                summary_lines.append(f"  [{url}]({url})")
                summary_lines.append("")

            summary = "\n".join(summary_lines)

            with open(os.path.join(out_dir, "collection.md"), "w", encoding="utf-8") as f:
                f.write(summary)

            duration = time.time() - start
            context.output_data = {
                "shared": {"raw_collection": summary},
                "artifacts": {"collection_json": json_path, "item_count": len(all_items)},
                "cost": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            print(f"[Data Collection] Complete in {duration:.1f}s — {len(all_items)} items")
            return PhaseResult(status=PhaseStatus.COMPLETED, context=context, timing={"total": duration})

        except Exception as exc:
            self._status = PhaseStatus.FAILED
            logger.error("AIWeekly collection failed: %s", exc, exc_info=True)
            return PhaseResult(status=PhaseStatus.FAILED, context=context, error=str(exc))

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        cfg = context.shared_state.get("task_config", {})
        if not cfg.get("date_from") or not cfg.get("date_to"):
            errors.append("date_from and date_to are required")
        return errors
