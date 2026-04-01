"""
Shared base for all RFP proposal generator phases.

Provides the common `_run_llm_stage` helper that every RFP phase calls.
Each phase subclass only needs to supply:
  - phase_type / display_name
  - a system prompt & user prompt builder
  - which shared-state keys it reads and writes
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
    """Resolve the default model from WorkflowConfig at import time."""
    try:
        from cmbagent.config import get_workflow_config
        return get_workflow_config().default_llm_model
    except Exception:
        return "gpt-4o"


@dataclass
class RfpPhaseConfig(PhaseConfig):
    """Shared config knobs for every RFP stage."""
    model: str = field(default_factory=_default_model)
    temperature: float = 0.7
    max_completion_tokens: int = 16384
    # Multi-turn: number of self-review iterations the LLM can do.
    # 0 = single-shot, 1+ = generate → review → refine loop.
    n_reviews: int = 1
    review_model: Optional[str] = None  # defaults to same as model
    # Multi-agent: enable 3-agent pipeline (primary → specialist → reviewer)
    multi_agent: bool = True
    specialist_model: Optional[str] = None  # override specialist model


class RfpPhaseBase(Phase):
    """
    Abstract helper that runs a two-pass generate→review cycle.

    Subclasses implement:
        build_user_prompt(context) -> str
        system_prompt -> str (property)
        shared_output_key -> str (property)
        output_filename -> str | None (property)
    """

    config: RfpPhaseConfig

    def __init__(self, config: RfpPhaseConfig = None):
        super().__init__(config)
        self.config: RfpPhaseConfig = config or RfpPhaseConfig(phase_type=self.phase_type)

    # ---- subclass hooks ----

    @property
    def system_prompt(self) -> str:
        """System-level instruction for the generation pass."""
        return (
            "You are a world-class technical proposal consultant. "
            "Produce detailed, professional, well-structured markdown documents."
        )

    @property
    def review_system_prompt(self) -> str:
        """System-level instruction for the review pass."""
        return (
            "You are a senior proposal reviewer at a top-tier consulting firm.  "
            "You will be given a draft document and must improve it to professional "
            "submission quality.  Specifically:\n"
            "1. Fix factual errors, strengthen weak sections, add missing detail\n"
            "2. Improve structure and flow, ensure proper section numbering\n"
            "3. Ensure ALL cost figures are present, consistent, and fit within any stated budget\n"
            "4. Verify every tool/technology has a comparison table vs alternatives with clear justification\n"
            "5. Verify security features are compared for each major tool and service\n"
            "6. Verify cloud provider comparison and justification sections are thorough\n"
            "7. Add professional tables where data is listed as bullets\n"
            "8. CRITICAL: Replace ANY placeholder text like '[Insert ...]', '[To be added]', "
            "'[Insert detailed cost tables]', '[Insert glossary]', or any bracket-enclosed "
            "placeholder with ACTUAL content derived from the document's own data.  "
            "Zero placeholders are acceptable in a final document.\n"
            "9. Ensure ALL monetary values use a single consistent currency throughout — no mixed currencies\n"
            "10. Verify every cost table has both Monthly and Annual columns with actual dollar figures in every cell — no empty cells\n"
            "11. Verify Annual Cost = Monthly Cost × 12 (fix any math errors)\n"
            "12. If the document has appendices, verify they contain REAL content (full tables, glossary entries, references) — not brief descriptions\n"
            "13. Ensure the document reads as a polished enterprise proposal — not an AI summary\n"
            "Return ONLY the improved markdown, no commentary."
        )

    @property
    def shared_output_key(self) -> str:  # pragma: no cover
        raise NotImplementedError

    @property
    def output_filename(self) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError

    def build_user_prompt(self, context: PhaseContext) -> str:  # pragma: no cover
        raise NotImplementedError

    # ---- specialist hook (multi-agent) ----

    @property
    def specialist_system_prompt(self) -> Optional[str]:
        """System-level instruction for the specialist agent.

        Override in subclasses to enable the specialist validation pass
        in multi-agent mode.  Return ``None`` to skip.
        """
        return None

    # ---- currency helper ----

    @staticmethod
    def get_currency_rule(context: PhaseContext) -> str:
        """Return a currency instruction derived from the requirements analysis.

        Scans the stage-1 output for the ## Currency section.  If not found,
        falls back to scanning the original RFP text for explicit currency
        mentions (e.g. "Indian Rupees", "INR", "₹").  Defaults to USD only
        when no currency signal is found anywhere.
        """
        import re

        # Known currency map: code -> symbol
        _CURRENCIES = {
            "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹",
            "AUD": "A$", "CAD": "C$", "JPY": "¥", "CNY": "¥",
            "SGD": "S$", "AED": "AED", "SAR": "SAR", "CHF": "CHF",
        }
        # Reverse: name -> code
        _NAME_TO_CODE = {
            "indian rupees": "INR", "indian rupee": "INR",
            "us dollars": "USD", "us dollar": "USD",
            "euros": "EUR", "euro": "EUR",
            "british pounds": "GBP", "british pound": "GBP",
            "pound sterling": "GBP", "pounds sterling": "GBP",
            "australian dollars": "AUD", "australian dollar": "AUD",
            "canadian dollars": "CAD", "canadian dollar": "CAD",
            "japanese yen": "JPY", "chinese yuan": "CNY",
            "singapore dollars": "SGD", "singapore dollar": "SGD",
        }

        code, symbol = None, None

        # --- Pass 1: structured output from requirements analysis ---
        reqs = context.shared_state.get("requirements_analysis", "")
        # Pattern A: **Primary Currency:** INR (₹)
        m = re.search(
            r"\*\*Primary Currency:\*\*\s*([A-Z]{3})\s*\(([^)]+)\)", reqs
        )
        if m:
            code, symbol = m.group(1), m.group(2)
        else:
            # Pattern B: looser — "Currency: INR" or "Currency — INR (₹)"
            m = re.search(
                r"(?:currency|payment)\s*[:—\-]\s*([A-Z]{3})", reqs, re.I
            )
            if m:
                code = m.group(1).upper()
                symbol = _CURRENCIES.get(code, code)

        # --- Pass 2: scan original RFP text for explicit currency mentions ---
        if not code:
            rfp_text = (context.task or "") + " " + reqs
            rfp_lower = rfp_text.lower()

            # Check for currency names ("Indian Rupees", "INR only", etc.)
            for name, c in _NAME_TO_CODE.items():
                if name in rfp_lower:
                    code, symbol = c, _CURRENCIES[c]
                    break

            # Check for ISO codes with context ("INR only", "payment in INR")
            if not code:
                m = re.search(
                    r"\b(INR|EUR|GBP|AUD|CAD|JPY|CNY|SGD|AED|SAR|CHF)\b",
                    rfp_text,
                )
                if m and m.group(1) != "USD":
                    code = m.group(1)
                    symbol = _CURRENCIES.get(code, code)

            # Check for symbols in the text (₹, €, £)
            if not code:
                for sym, c in [("₹", "INR"), ("€", "EUR"), ("£", "GBP")]:
                    if sym in rfp_text:
                        code, symbol = c, sym
                        break

        # --- Fallback ---
        if not code:
            code, symbol = "USD", "$"

        return (
            f"CURRENCY RULE: ALL monetary values in the ENTIRE document MUST be "
            f"in {code} ({symbol}) only. NEVER mix currencies. Every cost figure "
            f"must use the {symbol} symbol with {code} amounts.\n"
            f"COST TABLE FORMAT: Every cost table MUST have both Monthly Cost "
            f"({code}) and Annual Cost ({code}) columns with actual figures. "
            f"Annual = Monthly × 12. Never leave cost cells empty. "
            f"Format: {symbol}X,XXX with comma separators. "
            f"Every cost table MUST end with a **Total** row."
        )

    # ---- execution ----

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Run generate pass (with auto-chunking if needed), then optional review pass(es)."""
        from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider
        from cmbagent.phases.rfp.token_utils import (
            get_model_limits,
            count_tokens,
            chunk_prompt_if_needed,
        )

        self._status = PhaseStatus.RUNNING
        start = time.time()

        try:
            client = create_openai_client(timeout=300)
            model = self.config.model
            resolved = resolve_model_for_provider(model)
            _review_model_name = self.config.review_model or model
            review_model = resolve_model_for_provider(_review_model_name)

            # --- multi-agent model overrides ---
            if self.config.multi_agent:
                from cmbagent.phases.rfp.agent_teams import get_phase_models
                _agent_models = get_phase_models(self.phase_type)
                model = _agent_models.get("primary", model)
                resolved = resolve_model_for_provider(model)
                _review_model_name = _agent_models.get("reviewer", _review_model_name)
                review_model = resolve_model_for_provider(_review_model_name)
                _spec_model = self.config.specialist_model or _agent_models.get("specialist", _default_model())
                print(f"[{self.display_name}] Multi-agent: primary={model}, specialist={_spec_model}, reviewer={_review_model_name}")

            # Reasoning models (o3-*, o1-*) do not support the temperature param
            _is_reasoning = any(model.startswith(p) for p in ("o3", "o1"))
            _is_review_reasoning = any(_review_model_name.startswith(p) for p in ("o3", "o1"))

            user_prompt = self.build_user_prompt(context)

            # --- inject currency rule into every phase automatically ---
            currency_rule = self.get_currency_rule(context)
            if currency_rule not in user_prompt:
                user_prompt = user_prompt.rstrip() + "\n\n" + currency_rule

            # --- token capacity check ---
            max_ctx, max_out = get_model_limits(model)
            print(f"[{self.display_name}] Model {model}: context={max_ctx:,} tokens, max_output={max_out:,} tokens")

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
                # --- single-shot generation pass (prompt fits within limits) ---
                prompt_tokens = count_tokens(self.system_prompt + user_prompt, model)
                # Dynamically cap output tokens so prompt+output never exceeds context
                available_for_output = max_ctx - prompt_tokens - 200
                gen_max_tokens = min(self.config.max_completion_tokens, max(available_for_output, 4096))
                if gen_max_tokens < self.config.max_completion_tokens:
                    print(f"[{self.display_name}] Capping max_completion_tokens: {self.config.max_completion_tokens} → {gen_max_tokens} (prompt={prompt_tokens:,})")
                print(f"[{self.display_name}] Prompt fits within capacity ({prompt_tokens:,} tokens). Sending generation request to {model}...")

                def _gen():
                    params: dict = {
                        "model": resolved,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_completion_tokens": gen_max_tokens,
                    }
                    if not _is_reasoning:
                        params["temperature"] = self.config.temperature
                    return client.chat.completions.create(**params)

                gen_resp = await asyncio.to_thread(_gen)
                content = gen_resp.choices[0].message.content or ""
                finish_reason = gen_resp.choices[0].finish_reason
                print(f"[{self.display_name}] Generation complete ({len(content)} chars, finish_reason={finish_reason})")
                total_prompt += (gen_resp.usage.prompt_tokens if gen_resp.usage else 0)
                total_completion += (gen_resp.usage.completion_tokens if gen_resp.usage else 0)
            else:
                # --- chunked generation (prompt exceeds model capacity) ---
                print(f"[{self.display_name}] Prompt exceeds capacity — splitting into {len(chunks)} sub-requests...")
                partial_outputs: list[str] = []

                for idx, chunk in enumerate(chunks, 1):
                    chunk_tokens = count_tokens(chunk, model)
                    print(f"[{self.display_name}] Chunk {idx}/{len(chunks)} ({chunk_tokens:,} tokens)...")

                    # Provide context about which chunk this is so the LLM
                    # generates the right portion of the document.
                    if len(chunks) > 1:
                        chunk_instruction = (
                            f"\n\n---\n**NOTE:** This is part {idx} of {len(chunks)} of the source material. "
                            f"Generate the proposal sections that correspond to THIS portion of the source data. "
                            f"{'Continue from where the previous part left off. ' if idx > 1 else ''}"
                            f"Do NOT repeat content from earlier parts.\n"
                        )
                    else:
                        chunk_instruction = ""

                    def _gen_chunk(c=chunk, ci=chunk_instruction):
                        # Cap output tokens to fit within context
                        ck_prompt_tokens = count_tokens(self.system_prompt + c + ci, model) + 6
                        ck_available = max_ctx - ck_prompt_tokens - 200
                        ck_max = min(self.config.max_completion_tokens, max(ck_available, 4096))
                        params: dict = {
                            "model": resolved,
                            "messages": [
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": c + ci},
                            ],
                            "max_completion_tokens": ck_max,
                        }
                        if not _is_reasoning:
                            params["temperature"] = self.config.temperature
                        return client.chat.completions.create(**params)

                    resp = await asyncio.to_thread(_gen_chunk)
                    part = resp.choices[0].message.content or ""
                    partial_outputs.append(part)
                    print(f"[{self.display_name}] Chunk {idx} complete ({len(part)} chars)")
                    total_prompt += (resp.usage.prompt_tokens if resp.usage else 0)
                    total_completion += (resp.usage.completion_tokens if resp.usage else 0)

                # Combine all partial outputs
                content = "\n\n".join(partial_outputs)
                print(f"[{self.display_name}] All chunks combined ({len(content)} chars total)")

            # --- guard: skip review if generation produced nothing ---
            if not content or len(content) < 100:
                raise RuntimeError(
                    f"Generation produced insufficient content ({len(content)} chars). "
                    f"The model may have hit context limits or returned an empty response. "
                    f"Try using a model with a larger context window (e.g., gpt-4.1)."
                )

            # --- specialist pass (multi-agent) ---
            if self.config.multi_agent and self.specialist_system_prompt:
                content, _sp_tok, _sc_tok = await self._run_specialist(
                    client, content, context,
                )
                total_prompt += _sp_tok
                total_completion += _sc_tok

            # --- review passes ---
            for i in range(self.config.n_reviews):
                print(f"[{self.display_name}] Running review pass {i + 1}/{self.config.n_reviews}...")

                # Check if the review prompt also needs chunking
                review_prompt = f"Draft document:\n\n{content}"
                # Inject currency rule so the reviewer never changes currency
                review_prompt = review_prompt.rstrip() + "\n\n" + currency_rule
                review_chunks = chunk_prompt_if_needed(
                    system_prompt=self.review_system_prompt,
                    user_prompt=review_prompt,
                    model=self.config.review_model or model,
                    max_completion_tokens=self.config.max_completion_tokens,
                    safety_margin=0.75,
                )

                if review_chunks is None:
                    # Single-shot review — cap output tokens
                    rev_prompt_tokens = count_tokens(self.review_system_prompt + review_prompt, self.config.review_model or model) + 6
                    rev_available = max_ctx - rev_prompt_tokens - 200
                    rev_max_tokens = min(self.config.max_completion_tokens, max(rev_available, 4096))
                    if rev_max_tokens < self.config.max_completion_tokens:
                        print(f"[{self.display_name}] Review: capping max_completion_tokens {self.config.max_completion_tokens} → {rev_max_tokens}")

                    def _review(draft=content, _rmt=rev_max_tokens):
                        params: dict = {
                            "model": review_model,
                            "messages": [
                                {"role": "system", "content": self.review_system_prompt},
                                {"role": "user", "content": f"Draft document:\n\n{draft}"},
                            ],
                            "max_completion_tokens": _rmt,
                        }
                        if not _is_review_reasoning:
                            params["temperature"] = self.config.temperature
                        return client.chat.completions.create(**params)

                    rev_resp = await asyncio.to_thread(_review)
                    reviewed = rev_resp.choices[0].message.content or ""
                    # Only accept review if it produced substantial content
                    # (reject if reviewer returned meta-commentary instead of improved doc)
                    if reviewed and len(reviewed) > len(content) * 0.3:
                        content = reviewed
                    else:
                        print(f"[{self.display_name}] Review output too short ({len(reviewed)} chars vs {len(content)}) — keeping original")
                    total_prompt += (rev_resp.usage.prompt_tokens if rev_resp.usage else 0)
                    total_completion += (rev_resp.usage.completion_tokens if rev_resp.usage else 0)
                else:
                    # Chunked review
                    print(f"[{self.display_name}] Review draft exceeds capacity — splitting into {len(review_chunks)} sub-reviews...")
                    reviewed_parts: list[str] = []
                    for ridx, rchunk in enumerate(review_chunks, 1):
                        print(f"[{self.display_name}] Review chunk {ridx}/{len(review_chunks)}...")

                        def _review_chunk(rc=rchunk):
                            # Cap output tokens for this review chunk
                            rc_prompt_tok = count_tokens(self.review_system_prompt + rc, self.config.review_model or model) + 20
                            rc_avail = max_ctx - rc_prompt_tok - 200
                            rc_max = min(self.config.max_completion_tokens, max(rc_avail, 4096))
                            params: dict = {
                                "model": review_model,
                                "messages": [
                                    {"role": "system", "content": self.review_system_prompt},
                                    {"role": "user", "content": f"Draft document (part {ridx}/{len(review_chunks)}):\n\n{rc}"},
                                ],
                                "max_completion_tokens": rc_max,
                            }
                            if not _is_review_reasoning:
                                params["temperature"] = self.config.temperature
                            return client.chat.completions.create(**params)

                        rresp = await asyncio.to_thread(_review_chunk)
                        reviewed_parts.append(rresp.choices[0].message.content or rchunk)
                        total_prompt += (rresp.usage.prompt_tokens if rresp.usage else 0)
                        total_completion += (rresp.usage.completion_tokens if rresp.usage else 0)

                    content = "\n\n".join(reviewed_parts)

                print(f"[{self.display_name}] Review pass {i + 1} complete ({len(content)} chars)")

            # --- save to disk ---
            if self.output_filename:
                out_dir = os.path.join(context.work_dir, "input_files")
                os.makedirs(out_dir, exist_ok=True)
                fpath = os.path.join(out_dir, self.output_filename)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

            # --- build output ---
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
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                timing={"total": duration},
            )

        except Exception as exc:
            self._status = PhaseStatus.FAILED
            logger.error("RFP phase %s failed: %s", self.phase_type, exc, exc_info=True)
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(exc),
            )

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("task (RFP content) is required")
        return errors

    # ---- multi-agent: specialist pass ----

    async def _run_specialist(
        self, client, content: str, context: PhaseContext,
    ) -> tuple:
        """Run specialist agent to validate and enrich *content*.

        Uses the specialist model from ``PHASE_AGENT_MODELS`` (or
        ``config.specialist_model`` override) with full token safety.

        Returns:
            ``(content, prompt_tokens, completion_tokens)``
        """
        from cmbagent.llm_provider import resolve_model_for_provider
        from cmbagent.phases.rfp.token_utils import (
            get_model_limits, count_tokens, chunk_prompt_if_needed,
        )
        from cmbagent.phases.rfp.agent_teams import get_phase_models

        spec_prompt = self.specialist_system_prompt
        if not spec_prompt:
            return content, 0, 0

        models = get_phase_models(self.phase_type)
        spec_model = self.config.specialist_model or models.get("specialist", self.config.model)
        resolved_spec = resolve_model_for_provider(spec_model)
        _is_reasoning = any(spec_model.startswith(p) for p in ("o3", "o1"))

        max_ctx, _ = get_model_limits(spec_model)
        spec_user = f"Document to validate and improve:\n\n{content}"

        # Inject currency rule so the specialist never changes currency
        currency_rule = self.get_currency_rule(context)
        spec_user = spec_user.rstrip() + "\n\n" + currency_rule

        print(f"[{self.display_name}] Specialist agent ({spec_model}) validating content...")

        spec_chunks = chunk_prompt_if_needed(
            system_prompt=spec_prompt,
            user_prompt=spec_user,
            model=spec_model,
            max_completion_tokens=self.config.max_completion_tokens,
            safety_margin=0.75,
        )

        sp_total = 0
        sc_total = 0

        if spec_chunks is None:
            # ---- single-shot specialist ----
            prompt_tok = count_tokens(spec_prompt + spec_user, spec_model) + 6
            available = max_ctx - prompt_tok - 200
            spec_max = min(self.config.max_completion_tokens, max(available, 4096))
            if spec_max < self.config.max_completion_tokens:
                print(f"[{self.display_name}] Specialist: capping max_completion_tokens "
                      f"{self.config.max_completion_tokens} → {spec_max}")

            def _spec():
                params: dict = {
                    "model": resolved_spec,
                    "messages": [
                        {"role": "system", "content": spec_prompt},
                        {"role": "user", "content": spec_user},
                    ],
                    "max_completion_tokens": spec_max,
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
                print(f"[{self.display_name}] Specialist pass complete ({len(content)} chars)")
            else:
                print(f"[{self.display_name}] Specialist output too short "
                      f"({len(enriched)} chars vs {len(content)}) — keeping original")
        else:
            # ---- chunked specialist ----
            print(f"[{self.display_name}] Specialist content exceeds capacity — "
                  f"splitting into {len(spec_chunks)} sub-calls...")
            enriched_parts: list[str] = []
            for sidx, schunk in enumerate(spec_chunks, 1):
                def _spec_chunk(sc=schunk, si=sidx, total=len(spec_chunks)):
                    tok = count_tokens(spec_prompt + sc, spec_model) + 20
                    avail = max_ctx - tok - 200
                    cap = min(self.config.max_completion_tokens, max(avail, 4096))
                    params: dict = {
                        "model": resolved_spec,
                        "messages": [
                            {"role": "system", "content": spec_prompt},
                            {"role": "user", "content": (
                                f"Document section (part {si}/{total}) to validate "
                                f"and improve:\n\n{sc}"
                            )},
                        ],
                        "max_completion_tokens": cap,
                    }
                    if not _is_reasoning:
                        params["temperature"] = self.config.temperature
                    return client.chat.completions.create(**params)

                resp = await asyncio.to_thread(_spec_chunk)
                enriched_parts.append(resp.choices[0].message.content or schunk)
                sp_total += (resp.usage.prompt_tokens if resp.usage else 0)
                sc_total += (resp.usage.completion_tokens if resp.usage else 0)

            content = "\n\n".join(enriched_parts)
            print(f"[{self.display_name}] Chunked specialist pass complete ({len(content)} chars)")

        return content, sp_total, sc_total
