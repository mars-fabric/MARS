"""Phase 7 — Proposal Compilation.

Uses a **divide-and-accumulate** strategy for zero data loss:
- If all 6 source sections fit the context window → single generation call.
- If they don't fit → divide sources into groups that each fit, generate
  partial proposals per group, then run a final accumulation pass that
  merges all partial outputs into one cohesive document.
No source data is ever truncated, condensed, or dropped.
"""

import os
import time
import asyncio
import logging
from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext
from cmbagent.phases.base import PhaseResult, PhaseStatus

logger = logging.getLogger(__name__)


@dataclass
class RfpProposalConfig(RfpPhaseConfig):
    phase_type: str = "rfp_proposal"


class RfpProposalPhase(RfpPhaseBase):
    config_class = RfpProposalConfig

    def __init__(self, config=None):
        super().__init__(config or RfpProposalConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_proposal"

    @property
    def display_name(self) -> str:
        return "Proposal Compilation"

    @property
    def shared_output_key(self) -> str:
        return "proposal_compilation"

    @property
    def output_filename(self) -> str:
        return "proposal.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a world-class proposal writer who has authored winning proposals for "
            "Fortune 500 RFP responses worth $10M-$500M.  You produce polished, executive-ready "
            "documents that rival top-tier consulting firms (McKinsey, Deloitte, Accenture).  "
            "The final document must be comprehensive, professionally structured with clear "
            "section numbering, suitable for board-level presentation, and demonstrate deep "
            "technical competence while remaining accessible to non-technical stakeholders.  "
            "Use professional formatting: numbered sections and subsections (1.1, 1.2, etc.), "
            "tables for comparisons and costs, bullet points for clarity, and bold key terms."
        )

    @property
    def specialist_system_prompt(self) -> str:
        return (
            "You are a senior proposal editor at a Fortune 500 consulting firm "
            "specialising in RFP response quality assurance.  You will receive a "
            "compiled proposal document.  Validate and enrich it:\n"
            "1. Ensure document flow \u2014 does the narrative build logically from section to section?\n"
            "2. Validate section numbering and cross-references are consistent\n"
            "3. Check ALL cost tables: Monthly \u00d7 12 = Annual, subtotals add up, grand total is correct\n"
            "4. Ensure Executive Summary accurately reflects the full proposal content\n"
            "5. Verify appendices contain real, substantive content \u2014 not summaries or placeholders\n"
            "6. Check for any placeholder text ([Insert \u2026], [TBD], etc.) and replace with real content\n"
            "7. Validate technology selections, architecture, and timelines are internally consistent\n"
            "8. Polish prose to board-presentation quality \u2014 professional tone, no repetition\n"
            "Return the COMPLETE improved document \u2014 not a commentary.  Output clean markdown only."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        return self._build_full_prompt(context)

    def _get_sources(self, context: PhaseContext) -> dict:
        """Return the 6 source stage outputs."""
        ss = context.shared_state
        return {
            "requirements_analysis": ss.get("requirements_analysis", "(Not yet generated)"),
            "tools_technology": ss.get("tools_technology", "(Not yet generated)"),
            "cloud_infrastructure": ss.get("cloud_infrastructure", "(Not yet generated)"),
            "implementation_plan": ss.get("implementation_plan", "(Not yet generated)"),
            "architecture_design": ss.get("architecture_design", "(Not yet generated)"),
            "execution_strategy": ss.get("execution_strategy", "(Not yet generated)"),
        }

    def _build_full_prompt(self, context: PhaseContext, sources: dict | None = None) -> str:
        """Build the user prompt with full (or pre-condensed) source sections."""
        src = sources or self._get_sources(context)
        currency_rule = self.get_currency_rule(context)

        return f"""You are compiling a **comprehensive, professional technical proposal** in response to a detailed RFP.  This is NOT a summary — it is the FULL proposal document that will be submitted to the client.  It must be thorough, well-documented, and demonstrate mastery of every aspect.

Below are the detailed analyses from each prior stage.  You must synthesize ALL of this content — do not omit details, cost figures, timelines, or technical specifications.  Expand and enhance where needed.

---

### SOURCE: Requirements Analysis
{src["requirements_analysis"]}

---

### SOURCE: Tools & Technology Selection
{src["tools_technology"]}

---

### SOURCE: Cloud & Infrastructure Planning
{src["cloud_infrastructure"]}

---

### SOURCE: Implementation Plan
{src["implementation_plan"]}

---

### SOURCE: Architecture Design
{src["architecture_design"]}

---

### SOURCE: Execution Strategy
{src["execution_strategy"]}

---

Produce the COMPLETE proposal document with ALL of the following sections.  Each section must be substantive (not a brief paragraph — provide real depth and detail).

## Document Structure Required:

### 1. Cover Page
- Proposal title, date, version, "Prepared for [Client]" / "Prepared by [Organization]"
- Confidentiality notice

### 2. Executive Summary (1-2 pages)
- Business context and opportunity
- Solution overview in non-technical language
- Key differentiators of the proposed approach
- High-level cost summary and ROI projection
- Recommended timeline overview

### 3. Purpose & Introduction
- Clearly state the purpose of this proposal — how it addresses the project objectives and meets the RFP requirements
- Introduction to the proposing organisation and its mission
- Problem Statement — the client challenge this proposal solves
- Solution Overview — a concise narrative tying every section together
- Key Benefits to the client (cost savings, efficiency, risk reduction, etc.)
- Tips and recommendations for the client to maximise value from the proposed solution

### 4. Methodology
- Describe the methods, frameworks, and processes that will be used to complete the project
- Development methodology (Agile / SAFe / Waterfall / Hybrid) with justification
- Quality assurance approach and testing strategy
- Continuous integration / continuous delivery (CI/CD) practices
- Communication cadence and collaboration tools

### 5. Understanding of Requirements
- Demonstrate thorough understanding of the client's needs
- Map each major requirement to the proposed solution component
- Identify implicit requirements and how they are addressed
- Functional requirements summary table
- Non-functional requirements (performance, security, scalability, accessibility)
- Requirements traceability matrix (table format)

### 6. Proposed Solution Overview
- End-to-end solution narrative
- How all components work together
- Key architectural decisions and rationale
- Solution differentiators vs. alternative approaches

### 7. Technology Stack & Tooling
- Complete technology inventory table (tool, purpose, license type, annual cost)
- Selection criteria and evaluation process
- Justification for each major tool choice
- Integration architecture between tools

### 8. Cloud Infrastructure & Provider Selection
- **Cloud Provider Comparison** — Reproduce the comparison matrix from Stage 3
- **Selected Provider & Justification** — Why this provider was chosen (data-backed)
- **Why Other Providers Were Not Selected** — Specific reasons for each rejected provider
- Complete infrastructure blueprint with service-by-service mapping
- Detailed monthly and annual cost breakdown tables
- Cost optimization strategy and projected savings

### 9. System Architecture
- High-level architecture description (reference diagrams from Stage 5)
- Component-level design with responsibilities
- Data flow and integration patterns
- Security architecture and compliance controls
- Scalability and performance design
- Architecture Decision Records (ADRs) for key decisions

### 10. Timeline & Milestones
- Detailed project schedule with phases, milestones, and deliverables
- Sprint/iteration breakdown per phase
- Dependencies and critical path
- Gantt-style timeline table
- Key decision gates and client approval points

### 11. Resources
- Proposed team structure diagram
- Key personnel profiles (role, expertise, relevant experience)
- Headcount per phase
- Equipment, software, and material requirements
- Third-party vendors or subcontractors (if any)

### 12. Implementation Approach
- Phased delivery roadmap with milestones
- Go-live strategy and hypercare
- Knowledge transfer plan
- Change management process

### 13. Execution Plan
- Project governance structure
- Communication plan and cadence
- Escalation matrix
- Post-launch support and maintenance plan

### 14. Risk Management
- Risk register table (risk, probability, impact, mitigation, owner)
- Technical risks and mitigation
- Operational risks and mitigation
- Commercial risks and mitigation
- Contingency plans for top-5 risks

### 15. Qualifications & Experience
- Organisation credentials, certifications, and awards
- Relevant case studies / past projects of similar scope
- Client references (placeholder format)
- Key team member qualifications and certifications

### 16. Compliance
- How the proposal meets every requirement specified in the RFP
- Regulatory and industry compliance (ISO 27001, SOC 2, GDPR, HIPAA, etc.)
- Data residency and sovereignty considerations
- Accessibility standards (WCAG 2.1, Section 508)
- Compliance matrix mapping each RFP requirement to the proposal section that addresses it

### 17. Pricing Summary & Total Cost of Ownership
- Summary pricing table by category
- Detailed cost breakdown: infrastructure, licensing, personnel, support
- Year 1 / Year 2 / Year 3 TCO projection
- Payment schedule and milestones
- Value justification and ROI analysis

### 18. Terms, Assumptions & Constraints
- Key assumptions underlying the proposal
- Scope boundaries and exclusions
- Client responsibilities and dependencies

### 19. Supporting Information & Appendices
You MUST generate FULL, REAL content for each appendix — not summaries, not descriptions, not one-liners.

**Appendix A: Detailed Cost Breakdowns**
- Reproduce EVERY cost table from Sections 7, 8, and 17 into this appendix
- Create a consolidated master cost table with columns: Category | Service/Tool | Monthly Cost | Annual Cost
- Include ALL line items: every cloud service, every tool license, every personnel cost
- Show subtotals per category and a grand total row

**Appendix B: Technology Evaluation Matrices**
- Create a full evaluation matrix table for EACH technology category (Frontend, Backend, Database, DevOps, Monitoring, Security, etc.)
- Columns: Tool Name | Cost | Security Rating | License | Community/Support | Performance | Verdict (Selected/Rejected)
- Include every tool that was evaluated (both selected and rejected alternatives)
- Minimum 5-8 rows per matrix

**Appendix C: Supporting Charts & Data**
- Architecture diagrams described in text form
- Performance benchmarks and capacity planning data
- SLA targets table (availability, response time, RPO, RTO)
- Infrastructure sizing table (instance types, storage, bandwidth)

**Appendix D: Glossary of Terms and Acronyms**
- List EVERY technical term and acronym used in this proposal
- Format as a table: Term/Acronym | Full Form | Definition
- Include at minimum 20-30 entries

**Appendix E: References and Citations**
- List the actual standards, frameworks, and official documentation referenced: ISO 27001, SOC 2, GDPR, HIPAA, OWASP, NIST, AWS Well-Architected Framework, etc.
- Include links or citation format for each tool's official documentation
- Minimum 10-15 references

CRITICAL INSTRUCTIONS:
- This must read as a REAL, PROFESSIONAL proposal — not an AI-generated summary
- Use proper section numbering (1, 1.1, 1.2, 2, 2.1, etc.)
- Include ALL cost figures, timelines, and technical details from the source sections
- Use professional tables for all comparisons, costs, and matrices
- The cloud section MUST clearly differentiate the chosen provider and explain why others were rejected
- The technology section MUST include comparison tables showing each tool vs. alternatives and why it was chosen
- Include security comparison for every major tool and cloud service
- If the RFP specifies a budget, clearly show how ALL costs fit within that budget
- Minimum expected length: 3000+ words — be comprehensive, not brief
- Every section should have substantive content, not just placeholder text

{currency_rule}

COST TABLE FORMAT — MANDATORY:
- Every cost table MUST have both Monthly Cost and Annual Cost columns with actual figures
- Annual Cost = Monthly Cost x 12 (verify the math is correct)
- NEVER leave cost cells empty — every row must have an amount
- Format with comma separators for thousands
- NEVER put pipe characters inside a table cell
- Every cost table MUST end with a **Total** row summing all line items

ABSOLUTELY FORBIDDEN — NEVER DO THIS:
- NEVER use placeholder text like "[Insert ...]", "[To be added]", "[Insert detailed cost tables]", "[Insert glossary]", "[Insert references]", or any bracket-enclosed placeholder
- If you do not have specific data for a section, create it from the information available in the source sections above
- The Appendices section MUST contain REAL, COMPLETE content
- Every single section must have actual substantive content — zero placeholders allowed"""

    # ------------------------------------------------------------------
    # Source label mapping
    # ------------------------------------------------------------------
    _SOURCE_LABELS = {
        "requirements_analysis": "Requirements Analysis",
        "tools_technology": "Tools & Technology Selection",
        "cloud_infrastructure": "Cloud & Infrastructure Planning",
        "implementation_plan": "Implementation Plan",
        "architecture_design": "Architecture Design",
        "execution_strategy": "Execution Strategy",
    }

    # ------------------------------------------------------------------
    # Section assignments — which proposal sections come from which sources
    # ------------------------------------------------------------------
    _SOURCE_TO_SECTIONS = {
        "requirements_analysis": [
            "1. Cover Page", "2. Executive Summary", "3. Purpose & Introduction",
            "5. Understanding of Requirements",
        ],
        "tools_technology": [
            "7. Technology Stack & Tooling",
            "Appendix B: Technology Evaluation Matrices",
        ],
        "cloud_infrastructure": [
            "8. Cloud Infrastructure & Provider Selection",
            "Appendix A: Detailed Cost Breakdowns (cloud portion)",
        ],
        "implementation_plan": [
            "4. Methodology", "10. Timeline & Milestones",
            "11. Resources", "12. Implementation Approach",
        ],
        "architecture_design": [
            "6. Proposed Solution Overview", "9. System Architecture",
            "Appendix C: Supporting Charts & Data",
        ],
        "execution_strategy": [
            "13. Execution Plan", "14. Risk Management",
            "15. Qualifications & Experience", "16. Compliance",
            "17. Pricing Summary & Total Cost of Ownership",
            "18. Terms, Assumptions & Constraints",
            "19. Supporting Information & Appendices (D & E)",
        ],
    }

    def _build_partial_prompt(self, context: PhaseContext,
                               source_keys: list, sources: dict) -> str:
        """Build a prompt for a subset of sources, asking only for the
        proposal sections that correspond to those sources."""
        currency_rule = self.get_currency_rule(context)
        source_blocks = []
        section_list = []
        for key in source_keys:
            label = self._SOURCE_LABELS[key]
            source_blocks.append(f"### SOURCE: {label}\n{sources[key]}")
            section_list.extend(self._SOURCE_TO_SECTIONS.get(key, []))

        sources_text = "\n\n---\n\n".join(source_blocks)
        sections_text = "\n".join(f"- {s}" for s in section_list)

        return f"""You are compiling specific sections of a **comprehensive, professional technical proposal** in response to a detailed RFP.

Below are the source analyses relevant to YOUR assigned sections. Use ALL data — do not omit any details, cost figures, timelines, or technical specifications.

---

{sources_text}

---

Generate ONLY the following proposal sections (with full depth and detail):
{sections_text}

RULES:
- Use proper section numbering (1, 1.1, 1.2, etc.)
- Include ALL cost figures, timelines, and technical details from the sources
- Use professional tables for comparisons, costs, and matrices
{currency_rule}
- Every cost table MUST have Monthly Cost and Annual Cost columns with actual figures
- Annual Cost = Monthly Cost × 12 (verify math)
- NEVER use placeholder text like "[Insert ...]" or "[To be added]"
- Every section must have substantive content — zero placeholders allowed
- Output clean markdown only, no commentary"""

    # ------------------------------------------------------------------
    # Accumulation prompt — merges partial outputs into final document
    # ------------------------------------------------------------------
    _ACCUMULATE_SYSTEM = (
        "You are a senior proposal editor. You will be given multiple partial "
        "proposal documents that together cover all sections of a complete RFP "
        "response. Your job is to merge them into ONE cohesive, professionally "
        "structured document.\n\n"
        "RULES:\n"
        "- Preserve 100% of the content — do NOT drop, summarise, or shorten "
        "any section, table, cost figure, or data point\n"
        "- Fix section numbering to be sequential (1, 2, 3, ...)\n"
        "- Remove duplicate content if the same data appears in multiple parts\n"
        "- Ensure smooth transitions between sections\n"
        "- Ensure all appendices have FULL content (tables, glossary, references)\n"
        "- ALL monetary values in USD ($) only\n"
        "- Output the COMPLETE merged proposal as clean markdown — nothing else"
    )

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Stage 7: divide-and-accumulate execution — zero data loss.

        Strategy:
        1. Build full prompt with all 6 sources.
        2. If it fits → single generation call (no splitting needed).
        3. If it overflows → divide sources into groups that each fit the
           context window, generate partial proposals per group, then run
           a final accumulation pass to merge everything together.
        4. Review pass with content-length guard.
        """
        from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider
        from cmbagent.phases.rfp.token_utils import (
            get_effective_model_limits, count_tokens, group_sources_by_budget,
        )

        self._status = PhaseStatus.RUNNING
        start = time.time()

        try:
            client = create_openai_client(timeout=300)
            model = self.config.model
            resolved = resolve_model_for_provider(model)
            review_model = resolve_model_for_provider(self.config.review_model or model)

            _is_reasoning = any(model.startswith(p) for p in ("o3", "o1"))
            _is_review_reasoning = any(
                (self.config.review_model or model).startswith(p) for p in ("o3", "o1")
            )

            # Multi-agent model overrides
            if self.config.multi_agent:
                from cmbagent.phases.rfp.agent_teams import get_phase_models
                _agent_models = get_phase_models(self.phase_type)
                model = _agent_models.get("primary", model)
                resolved = resolve_model_for_provider(model)
                _review_model_name = _agent_models.get(
                    "reviewer", self.config.review_model or model,
                )
                review_model = resolve_model_for_provider(_review_model_name)
                _spec_model = _agent_models.get("specialist", "gpt-4.1-mini")
                _is_reasoning = any(model.startswith(p) for p in ("o3", "o1"))
                _is_review_reasoning = any(
                    _review_model_name.startswith(p) for p in ("o3", "o1")
                )
                # Sync config so _single_generate uses the correct model/limits
                self.config.model = model
                print(
                    f"[{self.display_name}] Multi-agent: primary={model}, "
                    f"specialist={_spec_model}, reviewer={_review_model_name}"
                )

            max_ctx, _ = get_effective_model_limits(model)
            # Use 0.75 safety margin — tiktoken can undercount by 10-20%
            # vs the API's actual tokenizer (special tokens, markdown, etc.)
            usable_ctx = int(max_ctx * 0.75) - self.config.max_completion_tokens
            sys_tokens = count_tokens(self.system_prompt, model)
            print(f"[{self.display_name}] Model {model}: context={max_ctx:,}, usable_for_prompt={usable_ctx:,}")

            sources = self._get_sources(context)
            user_prompt = self._build_full_prompt(context, sources=sources)
            user_tokens = count_tokens(user_prompt, model)
            total_tokens = sys_tokens + user_tokens + 6

            total_prompt_cost = 0
            total_completion_cost = 0

            print(f"[{self.display_name}] Full prompt: {total_tokens:,} tokens "
                  f"(system={sys_tokens:,}, user={user_tokens:,})")

            # ============================================================
            # PATH A: everything fits — single generation call
            # ============================================================
            content = ""
            if total_tokens <= usable_ctx:
                print(f"[{self.display_name}] Prompt fits. Single generation call...")
                content = await self._single_generate(
                    client, resolved, user_prompt, _is_reasoning,
                )
                total_prompt_cost += self._last_usage[0]
                total_completion_cost += self._last_usage[1]

                # If the API returned empty despite our estimate saying it fits,
                # the prompt is actually larger than tiktoken estimated.
                # Fall through to PATH B instead of crashing.
                if not content or len(content) < 200:
                    print(f"[{self.display_name}] PATH A returned {len(content)} chars "
                          f"(finish_reason={self._last_finish_reason}). "
                          f"Tiktoken likely undercounted. Falling back to PATH B...")
                    content = ""  # reset so PATH B runs

            # ============================================================
            # PATH B: divide-and-accumulate (runs if PATH A skipped or failed)
            # ============================================================
            if not content:
                print(f"[{self.display_name}] Prompt ({total_tokens:,}) exceeds "
                      f"usable context ({usable_ctx:,}) or PATH A failed")
                print(f"[{self.display_name}] Using divide-and-accumulate strategy "
                      f"(zero data loss)...")

                # The base prompt overhead = system + document-structure instructions
                # (everything except the source sections themselves)
                empty_sources = {k: "" for k in sources}
                base_prompt = self._build_full_prompt(context, sources=empty_sources)
                base_tokens = count_tokens(base_prompt, model) + sys_tokens + 10

                groups = group_sources_by_budget(
                    sources=sources,
                    base_prompt_tokens=base_tokens,
                    model=model,
                    max_completion_tokens=self.config.max_completion_tokens,
                    safety_margin=0.75,
                )

                print(f"[{self.display_name}] Divided {len(sources)} sources into "
                      f"{len(groups)} group(s)")

                partial_outputs: list[str] = []

                for g_idx, group_keys in enumerate(groups, 1):
                    labels = [self._SOURCE_LABELS[k] for k in group_keys]
                    print(f"[{self.display_name}] Group {g_idx}/{len(groups)}: "
                          f"{', '.join(labels)}")

                    # Always use partial prompt in PATH B — it is smaller
                    # than the full prompt and targeted to specific sections.
                    # Even with 1 group the full prompt already exceeded
                    # context, so the partial prompt (fewer instructions) is
                    # the safe choice.
                    partial_prompt = self._build_partial_prompt(
                        context, group_keys, sources,
                    )

                    partial = await self._single_generate(
                        client, resolved, partial_prompt, _is_reasoning,
                    )
                    total_prompt_cost += self._last_usage[0]
                    total_completion_cost += self._last_usage[1]
                    partial_outputs.append(partial)
                    print(f"[{self.display_name}]   → {len(partial)} chars generated")

                # --- accumulation pass: merge partial outputs ---
                if len(partial_outputs) == 1:
                    content = partial_outputs[0]
                else:
                    print(f"[{self.display_name}] Running accumulation pass to merge "
                          f"{len(partial_outputs)} partial outputs...")
                    numbered_parts = "\n\n".join(
                        f"{'='*60}\nPART {i+1} OF {len(partial_outputs)}\n{'='*60}\n\n{p}"
                        for i, p in enumerate(partial_outputs)
                    )
                    accumulate_prompt = (
                        f"Below are {len(partial_outputs)} partial proposal documents. "
                        f"Each covers different sections of the same RFP response. "
                        f"Merge them into ONE complete, cohesive proposal.\n\n"
                        f"Preserve 100% of the data — every table, cost figure, "
                        f"tool name, timeline, and section. Fix numbering and "
                        f"remove duplicates only.\n\n{numbered_parts}"
                    )

                    # Check if accumulation prompt fits
                    acc_tokens = (count_tokens(self._ACCUMULATE_SYSTEM, model)
                                  + count_tokens(accumulate_prompt, model) + 6)

                    if acc_tokens > usable_ctx:
                        # Accumulation prompt too large — just concatenate
                        # (still zero data loss, just less polished)
                        print(f"[{self.display_name}] Accumulation prompt ({acc_tokens:,} "
                              f"tokens) exceeds context — using direct concatenation")
                        content = "\n\n".join(partial_outputs)
                    else:
                        content = await self._single_generate(
                            client, resolved, accumulate_prompt, _is_reasoning,
                            system_override=self._ACCUMULATE_SYSTEM,
                        )
                        total_prompt_cost += self._last_usage[0]
                        total_completion_cost += self._last_usage[1]

                    print(f"[{self.display_name}] Accumulated output: {len(content)} chars")

            # --- guard: reject empty/tiny outputs ---
            finish_reason = self._last_finish_reason
            if not content or len(content) < 200:
                raise RuntimeError(
                    f"Generation produced insufficient content ({len(content)} chars, "
                    f"finish_reason={finish_reason}). Try a model with a larger context."
                )

            if finish_reason == "length":
                print(f"[{self.display_name}] WARNING: Output was truncated "
                      f"(hit max_completion_tokens={self.config.max_completion_tokens})")

            # --- specialist pass (multi-agent) ---
            if self.config.multi_agent and self.specialist_system_prompt:
                content, _sp_tok, _sc_tok = await self._run_specialist(
                    client, content, context,
                )
                total_prompt_cost += _sp_tok
                total_completion_cost += _sc_tok

            # --- review pass (with overflow protection) ---
            from cmbagent.phases.rfp.token_utils import chunk_prompt_if_needed, count_tokens as _count

            for i in range(self.config.n_reviews):
                print(f"[{self.display_name}] Running review pass "
                      f"{i + 1}/{self.config.n_reviews}...")

                review_user = f"Draft document:\n\n{content}"
                rev_model_name = self.config.review_model or model
                review_chunks = chunk_prompt_if_needed(
                    system_prompt=self.review_system_prompt,
                    user_prompt=review_user,
                    model=rev_model_name,
                    max_completion_tokens=self.config.max_completion_tokens,
                    safety_margin=0.75,
                )

                if review_chunks is None:
                    # Single-shot review — cap output tokens
                    rev_ptok = _count(self.review_system_prompt + review_user, rev_model_name) + 6
                    rev_avail = max_ctx - rev_ptok - 200
                    rev_max = min(self.config.max_completion_tokens, max(rev_avail, 4096))
                    if rev_max < self.config.max_completion_tokens:
                        print(f"[{self.display_name}] Review: capping max_completion_tokens "
                              f"{self.config.max_completion_tokens} → {rev_max}")

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
                    rev_finish = rev_resp.choices[0].finish_reason
                    total_prompt_cost += (rev_resp.usage.prompt_tokens if rev_resp.usage else 0)
                    total_completion_cost += (rev_resp.usage.completion_tokens if rev_resp.usage else 0)

                    if reviewed and len(reviewed) > len(content) * 0.5:
                        content = reviewed
                        print(f"[{self.display_name}] Review pass {i+1} complete: "
                              f"{len(content)} chars, finish_reason={rev_finish}")
                    else:
                        print(f"[{self.display_name}] Review pass {i+1} weak output "
                              f"({len(reviewed)} chars) — keeping previous output")
                else:
                    # Chunked review — draft too large for single call
                    print(f"[{self.display_name}] Review draft exceeds capacity — "
                          f"splitting into {len(review_chunks)} sub-reviews...")
                    reviewed_parts: list[str] = []
                    for ridx, rchunk in enumerate(review_chunks, 1):
                        def _rev_chunk(rc=rchunk, ri=ridx, total=len(review_chunks)):
                            # Cap output tokens for this review chunk
                            rc_ptok = _count(self.review_system_prompt + rc, rev_model_name) + 20
                            rc_avail = max_ctx - rc_ptok - 200
                            rc_max = min(self.config.max_completion_tokens, max(rc_avail, 4096))
                            params: dict = {
                                "model": review_model,
                                "messages": [
                                    {"role": "system", "content": self.review_system_prompt},
                                    {"role": "user", "content": (
                                        f"Draft document (part {ri}/{total}):\n\n{rc}"
                                    )},
                                ],
                                "max_completion_tokens": rc_max,
                            }
                            if not _is_review_reasoning:
                                params["temperature"] = self.config.temperature
                            return client.chat.completions.create(**params)

                        rresp = await asyncio.to_thread(_rev_chunk)
                        reviewed_parts.append(
                            rresp.choices[0].message.content or rchunk
                        )
                        total_prompt_cost += (rresp.usage.prompt_tokens if rresp.usage else 0)
                        total_completion_cost += (rresp.usage.completion_tokens if rresp.usage else 0)

                    content = "\n\n".join(reviewed_parts)
                    print(f"[{self.display_name}] Chunked review pass {i+1} complete: "
                          f"{len(content)} chars")

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
                    "prompt_tokens": total_prompt_cost,
                    "completion_tokens": total_completion_cost,
                    "total_tokens": total_prompt_cost + total_completion_cost,
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
            logger.error("RFP proposal phase failed: %s", exc, exc_info=True)
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Helper: single LLM generation call
    # ------------------------------------------------------------------
    _last_usage: tuple = (0, 0)
    _last_finish_reason: str = ""

    async def _single_generate(self, client, resolved: str, user_prompt: str,
                                is_reasoning: bool,
                                system_override: str | None = None) -> str:
        """Fire a single generation call and store usage/finish_reason.

        Dynamically caps max_completion_tokens so prompt + output never
        exceeds the model's context window.
        """
        from cmbagent.phases.rfp.token_utils import count_tokens, get_effective_model_limits

        sys_prompt = system_override or self.system_prompt
        model = self.config.model
        max_ctx, _ = get_effective_model_limits(model)

        # Estimate prompt tokens and cap output to stay within context
        prompt_tokens = (count_tokens(sys_prompt, model)
                         + count_tokens(user_prompt, model) + 6)
        available_for_output = max_ctx - prompt_tokens - 200  # 200 token safety buffer
        max_comp = min(self.config.max_completion_tokens, max(available_for_output, 4096))

        if max_comp < self.config.max_completion_tokens:
            print(f"[{self.display_name}] Capping max_completion_tokens: "
                  f"{self.config.max_completion_tokens} → {max_comp} "
                  f"(prompt={prompt_tokens:,}, context={max_ctx:,})")

        def _call():
            params: dict = {
                "model": resolved,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_completion_tokens": max_comp,
            }
            if not is_reasoning:
                params["temperature"] = self.config.temperature
            return client.chat.completions.create(**params)

        resp = await asyncio.to_thread(_call)
        content = resp.choices[0].message.content or ""
        self._last_finish_reason = resp.choices[0].finish_reason or ""
        self._last_usage = (
            resp.usage.prompt_tokens if resp.usage else 0,
            resp.usage.completion_tokens if resp.usage else 0,
        )
        return content
