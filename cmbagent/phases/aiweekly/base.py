"""
Shared base for AI Weekly Report phases.

Provides AIWeeklyPhaseBase with the same generate → specialist → review
pipeline used by RFP phases, plus token chunking at every LLM call.
"""

import os
import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus

logger = logging.getLogger(__name__)


def _default_model() -> str:
    try:
        from cmbagent.config import get_workflow_config
        return get_workflow_config().default_llm_model
    except Exception:
        return "gpt-4o"


@dataclass
class AIWeeklyPhaseConfig(PhaseConfig):
    """Config for AI Weekly phases."""
    model: str = field(default_factory=_default_model)
    temperature: float = 0.7
    max_completion_tokens: int = 16384
    n_reviews: int = 1
    review_model: Optional[str] = None
    multi_agent: bool = True
    specialist_model: Optional[str] = None


@dataclass
class AIWeeklyTaskConfig:
    """User-facing task configuration passed from the frontend."""
    date_from: str = ""
    date_to: str = ""
    topics: List[str] = field(default_factory=lambda: ["llm", "cv"])
    sources: List[str] = field(default_factory=lambda: [
        "github", "press-releases", "company-announcements",
        "major-releases", "curated-ai-websites",
    ])
    style: str = "concise"  # concise | detailed | technical


class AIWeeklyPhaseBase(Phase):
    """
    Abstract base for AI Weekly phases (Stages 2–4).

    Stage 1 (Data Collection) uses a separate non-LLM class.
    Stages 2–4 use this base with generate → specialist → review.
    """

    config: AIWeeklyPhaseConfig

    def __init__(self, config: AIWeeklyPhaseConfig = None):
        super().__init__(config)
        self.config: AIWeeklyPhaseConfig = config or AIWeeklyPhaseConfig(
            phase_type=self.phase_type
        )

    # ── subclass hooks ──

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior AI industry analyst producing a professional "
            "weekly report for enterprise distribution."
        )

    @property
    def review_system_prompt(self) -> str:
        return (
            "You are a senior editor and fact-checker reviewing an AI Weekly Report draft.\n"
            "1. Fix factual errors and weak analysis\n"
            "2. Ensure every item has date (YYYY-MM-DD), source link, and ≥100-word description\n"
            "3. Remove duplicates — each release appears exactly once\n"
            "4. Verify the report has exactly 4 sections: Executive Summary, "
            "Key Highlights, Trends, Quick Reference Table\n"
            "5. Replace any placeholder text with real content\n"
            "6. Ensure professional tone suitable for executive distribution\n"
            "7. HALLUCINATION CHECK — Remove any item or fact not traceable to source data\n"
            "8. PRODUCT NAMES — Remove invented product/model names not in source data\n"
            "9. DATE CHECK — Remove items with unverifiable or out-of-range dates\n"
            "10. METRIC CHECK — Remove unverified performance numbers and statistics\n"
            "11. CLAIMS CHECK — Strip unattributed superlatives (breakthrough, revolutionary, etc.)\n"
            "Return ONLY the improved markdown, no commentary."
        )

    @property
    def specialist_system_prompt(self) -> Optional[str]:
        return None

    @property
    def shared_output_key(self) -> str:
        raise NotImplementedError

    @property
    def output_filename(self) -> Optional[str]:
        raise NotImplementedError

    def build_user_prompt(self, context: PhaseContext) -> str:
        raise NotImplementedError

    # ── style rule helper ──

    @staticmethod
    def get_style_rule(context: PhaseContext) -> str:
        style = (context.shared_state.get("task_config") or {}).get("style", "concise")
        rules = {
            "concise": "STYLE: CONCISE — Each item gets a brief overview (2-4 sentences, ~50-80 words). "
                       "Focus on WHAT happened and WHO is involved. No deep analysis needed.",
            "detailed": "STYLE: DETAILED — Each item description must be ≥130 words. Include deep analysis, "
                        "competitive context, business implications, and why it matters strategically.",
            "technical": "STYLE: TECHNICAL — Each item description must be ≥130 words with concrete metrics, "
                         "implementation details, architecture specifics, and technical depth.",
        }
        return f"STYLE RULE: {rules.get(style, rules['concise'])}"

    # ── execution (same pattern as RFP) ──

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider
        from cmbagent.phases.rfp.token_utils import (
            get_model_limits, count_tokens, chunk_prompt_if_needed,
        )

        self._status = PhaseStatus.RUNNING
        start = time.time()

        try:
            client = create_openai_client(timeout=300)
            model = self.config.model
            resolved = resolve_model_for_provider(model)
            _review_model_name = self.config.review_model or model
            review_model = resolve_model_for_provider(_review_model_name)

            if self.config.multi_agent:
                _spec_model = self.config.specialist_model or model

            _is_reasoning = any(model.startswith(p) for p in ("o3", "o1"))
            _is_review_reasoning = any(_review_model_name.startswith(p) for p in ("o3", "o1"))

            user_prompt = self.build_user_prompt(context)
            style_rule = self.get_style_rule(context)
            if style_rule not in user_prompt:
                user_prompt = user_prompt.rstrip() + "\n\n" + style_rule

            max_ctx, max_out = get_model_limits(model)
            print(f"[{self.display_name}] Model {model}: context={max_ctx:,}, max_output={max_out:,}")

            chunks = chunk_prompt_if_needed(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_completion_tokens=self.config.max_completion_tokens,
                safety_margin=0.75,
            )

            total_prompt = 0
            total_completion = 0

            if chunks is None:
                # Single-shot generation
                prompt_tokens = count_tokens(self.system_prompt + user_prompt, model)
                available_for_output = max_ctx - prompt_tokens - 200
                gen_max = min(self.config.max_completion_tokens, max(available_for_output, 4096))
                print(f"[{self.display_name}] Single-shot ({prompt_tokens:,} tokens, max_out={gen_max:,})")

                def _gen():
                    params: dict = {
                        "model": resolved,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_completion_tokens": gen_max,
                    }
                    if not _is_reasoning:
                        params["temperature"] = self.config.temperature
                    return client.chat.completions.create(**params)

                resp = await asyncio.to_thread(_gen)
                content = resp.choices[0].message.content or ""
                total_prompt += (resp.usage.prompt_tokens if resp.usage else 0)
                total_completion += (resp.usage.completion_tokens if resp.usage else 0)
                print(f"[{self.display_name}] Generation complete ({len(content)} chars)")
            else:
                # Chunked generation
                print(f"[{self.display_name}] Chunked into {len(chunks)} parts")
                parts: list[str] = []
                for idx, chunk in enumerate(chunks, 1):
                    def _gen_chunk(c=chunk, i=idx, t=len(chunks)):
                        tok = count_tokens(self.system_prompt + c, model) + 6
                        avail = max_ctx - tok - 200
                        cap = min(self.config.max_completion_tokens, max(avail, 4096))
                        params: dict = {
                            "model": resolved,
                            "messages": [
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": c},
                            ],
                            "max_completion_tokens": cap,
                        }
                        if not _is_reasoning:
                            params["temperature"] = self.config.temperature
                        return client.chat.completions.create(**params)

                    resp = await asyncio.to_thread(_gen_chunk)
                    parts.append(resp.choices[0].message.content or "")
                    total_prompt += (resp.usage.prompt_tokens if resp.usage else 0)
                    total_completion += (resp.usage.completion_tokens if resp.usage else 0)
                content = "\n\n".join(parts)

            if not content or len(content) < 100:
                raise RuntimeError(f"Generation produced insufficient content ({len(content)} chars)")

            # Specialist pass
            if self.config.multi_agent and self.specialist_system_prompt:
                content, sp, sc = await self._run_specialist(client, content, context)
                total_prompt += sp
                total_completion += sc

            # Review pass
            for i in range(self.config.n_reviews):
                print(f"[{self.display_name}] Review pass {i + 1}/{self.config.n_reviews}")
                review_prompt = f"Draft document:\n\n{content}\n\n{style_rule}"
                rev_chunks = chunk_prompt_if_needed(
                    system_prompt=self.review_system_prompt,
                    user_prompt=review_prompt,
                    model=_review_model_name,
                    max_completion_tokens=self.config.max_completion_tokens,
                    safety_margin=0.75,
                )

                if rev_chunks is None:
                    rev_tok = count_tokens(self.review_system_prompt + review_prompt, _review_model_name) + 6
                    rev_avail = max_ctx - rev_tok - 200
                    rev_max = min(self.config.max_completion_tokens, max(rev_avail, 4096))

                    def _review(draft=content, _rm=rev_max):
                        params: dict = {
                            "model": review_model,
                            "messages": [
                                {"role": "system", "content": self.review_system_prompt},
                                {"role": "user", "content": f"Draft document:\n\n{draft}"},
                            ],
                            "max_completion_tokens": _rm,
                        }
                        if not _is_review_reasoning:
                            params["temperature"] = self.config.temperature
                        return client.chat.completions.create(**params)

                    rev_resp = await asyncio.to_thread(_review)
                    reviewed = rev_resp.choices[0].message.content or ""
                    if reviewed and len(reviewed) > len(content) * 0.3:
                        content = reviewed
                    total_prompt += (rev_resp.usage.prompt_tokens if rev_resp.usage else 0)
                    total_completion += (rev_resp.usage.completion_tokens if rev_resp.usage else 0)

            # Save
            if self.output_filename:
                out_dir = os.path.join(context.work_dir, "input_files")
                os.makedirs(out_dir, exist_ok=True)
                with open(os.path.join(out_dir, self.output_filename), "w", encoding="utf-8") as f:
                    f.write(content)

            duration = time.time() - start
            context.output_data = {
                "shared": {self.shared_output_key: content},
                "artifacts": {"model": model},
                "cost": {
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "total_tokens": total_prompt + total_completion,
                },
            }
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(status=PhaseStatus.COMPLETED, context=context, timing={"total": duration})

        except Exception as exc:
            self._status = PhaseStatus.FAILED
            logger.error("AIWeekly phase %s failed: %s", self.phase_type, exc, exc_info=True)
            return PhaseResult(status=PhaseStatus.FAILED, context=context, error=str(exc))

    # ── specialist pass ──

    async def _run_specialist(self, client, content: str, context: PhaseContext) -> tuple:
        from cmbagent.llm_provider import resolve_model_for_provider
        from cmbagent.phases.rfp.token_utils import (
            get_model_limits, count_tokens, chunk_prompt_if_needed,
        )

        spec_prompt = self.specialist_system_prompt
        if not spec_prompt:
            return content, 0, 0

        spec_model = self.config.specialist_model or self.config.model
        resolved_spec = resolve_model_for_provider(spec_model)
        _is_reasoning = any(spec_model.startswith(p) for p in ("o3", "o1"))
        max_ctx, _ = get_model_limits(spec_model)

        spec_user = f"Document to validate and improve:\n\n{content}"
        print(f"[{self.display_name}] Specialist ({spec_model}) validating...")

        spec_chunks = chunk_prompt_if_needed(
            system_prompt=spec_prompt,
            user_prompt=spec_user,
            model=spec_model,
            max_completion_tokens=self.config.max_completion_tokens,
            safety_margin=0.75,
        )

        sp_total, sc_total = 0, 0

        if spec_chunks is None:
            tok = count_tokens(spec_prompt + spec_user, spec_model) + 6
            avail = max_ctx - tok - 200
            cap = min(self.config.max_completion_tokens, max(avail, 4096))

            def _spec():
                params: dict = {
                    "model": resolved_spec,
                    "messages": [
                        {"role": "system", "content": spec_prompt},
                        {"role": "user", "content": spec_user},
                    ],
                    "max_completion_tokens": cap,
                }
                if not _is_reasoning:
                    params["temperature"] = self.config.temperature
                return client.chat.completions.create(**params)

            resp = await asyncio.to_thread(_spec)
            enriched = resp.choices[0].message.content or ""
            sp_total += (resp.usage.prompt_tokens if resp.usage else 0)
            sc_total += (resp.usage.completion_tokens if resp.usage else 0)

            if enriched and len(enriched) > len(content) * 0.3:
                content = enriched
                print(f"[{self.display_name}] Specialist complete ({len(content)} chars)")
            else:
                print(f"[{self.display_name}] Specialist output too short, keeping original")

        return content, sp_total, sc_total

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("task configuration is required")
        return errors
