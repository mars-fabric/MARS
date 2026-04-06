"""
PDA task-framework helpers — Production Grade v2.

Stage 1 (Research Summary) supports two research modes:
  one_shot              – cmbagent.one_shot(agent='researcher') + direct LLM fallback
  planning_and_control  – planning_and_control_context_carryover() with planner/researcher

Stages 2-7 use direct LLM structured generation with rich, deep prompts.
Each section is designed to return 7-8 items minimum with full supporting context.

All print() calls are captured by _ConsoleCapture in the router and streamed
to the frontend via WebSocket / HTTP poll.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Default model assignments — loaded from model_config.yaml via registry ──

def _get_research_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_stage_defaults("pda", 1)

# ---------------------------------------------------------------------------
# Shared system prompt
# ---------------------------------------------------------------------------
_SYSTEM_STRATEGIST = """\
You are a Principal Product Discovery Strategist at a Tier-1 strategy consulting firm \
(equivalent to McKinsey, Bain, BCG, Deloitte). You specialise in enterprise digital \
transformation, product strategy, and evidence-based opportunity discovery. \

ABSOLUTE RULES:
1. Use ONLY real, verifiable, publicly documented data. Every statistic, market size, \
   competitor move, and trend MUST reference a real source (Gartner, McKinsey, Forrester, \
   Statista, IDC, PwC, Deloitte, earnings calls, SEC filings, Bloomberg, Reuters, \
   industry-specific publications).
2. NEVER fabricate numbers, company names, statistics, or source citations.
3. Return ONLY valid, parseable JSON — no markdown fences, no prose outside JSON.
4. Every array in your response MUST contain the requested minimum number of items. \
   Providing fewer items is a CRITICAL failure.
5. All content must be consultant-quality: specific, actionable, evidence-backed.\
"""

# Separate system prompt for stage 7 — Markdown slide content (NOT JSON)
_SYSTEM_PRESENTER = """\
You are a Principal Product Discovery Strategist at a Tier-1 strategy consulting firm \
(equivalent to McKinsey, Bain, BCG, Deloitte). You are preparing an executive-quality \
slide deck for a C-suite product discovery presentation.

ABSOLUTE RULES:
1. Use ONLY real, verifiable, publicly documented data referenced to actual sources.
2. NEVER fabricate numbers, statistics, or citations.
3. Return ONLY valid Markdown — use ## for slide titles, - for bullet points, \
   > for speaker notes. Do NOT return JSON. Do NOT add markdown code fences.
4. Every slide MUST have 7-8 substantive, specific, consultant-quality bullet points.
5. Every slide MUST have speaker notes in > blockquote format.
6. All content must be specific and actionable — no vague statements.\
"""


# ---------------------------------------------------------------------------
# LLM call  (max_token-aware, with o-series fallback)
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, system: str = None, max_tokens: int = 12000) -> str:
    """Direct LLM call via cmbagent provider infrastructure."""
    from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider

    client = create_openai_client()
    from cmbagent.config.model_registry import get_model_registry
    _default_model = get_model_registry().get_stage_defaults("pda", 2).get("llm_model", "gpt-4o")
    model = resolve_model_for_provider(os.getenv("CMBAGENT_DEFAULT_MODEL", _default_model))

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    print(f"[PDA] Calling LLM  model={model}  prompt_len={len(prompt)}")

    for use_ct in (True, False):
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
            }
            if use_ct:
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            print(f"[PDA] LLM response received  len={len(content)}")
            return content
        except Exception as e:
            err = str(e)
            if use_ct and ("max_tokens" in err or "completion_tokens" in err):
                continue
            raise


# ---------------------------------------------------------------------------
# JSON extraction (robust — handles fenced blocks, trailing characters)
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> Optional[dict]:
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_array(text: str) -> Optional[list]:
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _repair_json_array(text: str) -> Optional[list]:
    """
    Recover items from a truncated or malformed JSON array.

    Strategy: walk the raw text character by character, extract every
    syntactically complete top-level ``{...}`` object, and return the list
    of successfully-parsed objects.  This handles responses that are cut off
    mid-array because the LLM hit its token budget.
    """
    # Strip fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text).strip()

    # Find the opening bracket
    start = text.find("[")
    if start == -1:
        return None
    body = text[start + 1:]  # everything after the opening `[`

    items: list = []
    depth = 0
    in_string = False
    escape_next = False
    obj_start: Optional[int] = None

    for i, c in enumerate(body):
        if escape_next:
            escape_next = False
            continue
        if c == "\\" and in_string:
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if c == "{":
            if depth == 0:
                obj_start = i  # beginning of a top-level object
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and obj_start is not None:
                # We have a syntactically complete object — try to parse it
                candidate = body[obj_start: i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        items.append(obj)
                except json.JSONDecodeError:
                    pass
                obj_start = None
        elif c == "]" and depth == 0:
            break  # reached the proper end of the array

    return items if items else None


def _extract_json_array_robust(text: str) -> Optional[list]:
    """Try standard extraction first; fall back to truncation repair."""
    result = _extract_json_array(text)
    if result is not None:
        return result
    return _repair_json_array(text)


# ---------------------------------------------------------------------------
# Intake helper
# ---------------------------------------------------------------------------

def _get_intake(ss: dict) -> dict:
    return {
        "client_name":            ss.get("client_name", ""),
        "industry":               ss.get("industry", ""),
        "sub_industry":           ss.get("sub_industry", ""),
        "client_context":         ss.get("client_context", ""),
        "business_function":      ss.get("business_function", ""),
        "discovery_type":         ss.get("discovery_type", ""),
        "process_type":           ss.get("process_type", "new"),
        "existing_functionality": ss.get("existing_functionality", ""),
        "problem_keywords":       ss.get("problem_keywords", ""),
        "expected_output":        ss.get("expected_output", []),
    }


# ---------------------------------------------------------------------------
# Stage dispatcher  (stages 2-7 — stage 1 goes through router)
# ---------------------------------------------------------------------------

def run_stage(stage_num: int, shared_state: dict, work_dir: str) -> dict:
    """Dispatch to the correct stage handler (called by router for stages 2-7)."""
    handlers = {
        2: _stage_problem_definition,
        3: _stage_opportunities,
        4: _stage_solution_archetypes,
        5: _stage_features,
        6: _stage_prompts,
        7: _stage_slide_content,
    }
    handler = handlers.get(stage_num)
    if not handler:
        raise ValueError(f"Unknown PDA stage number: {stage_num}")
    return handler(shared_state, work_dir)


# ---------------------------------------------------------------------------
# Stage 1 — Research Summary helpers  (called from router, not run_stage)
# ---------------------------------------------------------------------------

def _call_one_shot_researcher(task: str, work_dir: str, api_keys: dict | None = None) -> Optional[str]:
    """Call cmbagent.one_shot with researcher agent. Returns raw text or None."""
    import uuid as _uuid
    try:
        import cmbagent
        from cmbagent.utils import get_api_keys_from_env
    except ImportError as e:
        logger.warning("[PDA] cmbagent not available: %s", e)
        return None

    run_dir = os.path.join(work_dir, f"one_shot_{_uuid.uuid4().hex[:8]}")
    os.makedirs(run_dir, exist_ok=True)
    if api_keys is None:
        api_keys = get_api_keys_from_env()

    print(f"[PDA] Starting one_shot researcher  work_dir={run_dir}")
    try:
        results = cmbagent.one_shot(
            task=task,
            agent="researcher",
            max_rounds=20,
            max_n_attempts=3,
            work_dir=run_dir,
            api_keys=api_keys,
            clear_work_dir=False,
        )
    except Exception as e:
        logger.warning("[PDA] one_shot failed: %s", e)
        for fname in (os.listdir(run_dir) if os.path.isdir(run_dir) else []):
            if fname.endswith((".md", ".txt", ".json")):
                try:
                    with open(os.path.join(run_dir, fname)) as f:
                        c = f.read()
                    if c.strip():
                        print(f"[PDA] Salvaged output from {fname}")
                        return c
                except Exception:
                    pass
        return None

    chat_history = results.get("chat_history", [])
    for msg in chat_history:
        if not isinstance(msg, dict):
            continue
        name = msg.get("name", "")
        content = msg.get("content", "")
        if not content or content == "None":
            continue
        if isinstance(content, str) and any(p in content.lower() for p in [
            "has been marked as failed", "exitcode: 1", "execution failed",
        ]):
            continue
        if name in ("researcher", "researcher_response_formatter") and len(content.strip()) > 100:
            print(f"[PDA] Extracted researcher output  len={len(content)}")
            return content

    final_ctx = results.get("final_context", {})
    if isinstance(final_ctx, dict):
        for key in ("previous_steps_execution_summary", "researcher_output", "response", "result"):
            val = final_ctx.get(key)
            if val and isinstance(val, str) and len(val.strip()) > 100:
                return val
    return None


def _format_research_as_json(raw_text: str, intake: dict) -> dict:
    """Convert researcher freeform output into deep structured JSON (8 items per section)."""
    biz_fn = intake["business_function"]
    client = intake["client_name"]
    industry = intake["industry"]
    prompt = f"""\
You are a JSON formatter. Extract and DEEPLY structure the following market research notes \
about {client} in the {industry} industry into the exact JSON schema below.

Research Notes:
{raw_text[:8000]}

Requirements:
- marketTrends: EXACTLY 7-8 items, each with title, description (2 sentences with statistics), \
  impactLevel (High/Medium/Low), timeframe, and source
- competitorMoves: EXACTLY 6-7 items, each with company, action, implication, and source
- industryPainPoints: EXACTLY 7-8 items, each with pain, severity \
  (Critical/High/Medium), description, affectedPersonas array, and source
- workshopAngles: EXACTLY 5-6 items, each with hmw, rationale, expectedOutcome
- keyStatistics: EXACTLY 6-8 items — specific quantified statistics with source and year
- references: EXACTLY 7-8 full citations

Return ONLY valid JSON matching this EXACT schema:
{{
  "executiveSummary": "4-5 sentence executive summary of the market landscape and key findings",
  "marketTrends": [
    {{
      "title": "Trend title",
      "description": "2-3 sentences with specific statistics from the research",
      "impactLevel": "High",
      "timeframe": "Short-term|Medium-term|Long-term",
      "source": "Source name and year"
    }}
  ],
  "competitorMoves": [
    {{
      "company": "Company name",
      "action": "Specific action taken",
      "implication": "Strategic implication for {client}",
      "source": "Source and year"
    }}
  ],
  "industryPainPoints": [
    {{
      "pain": "Pain point title",
      "severity": "Critical",
      "description": "2 sentences with quantified impact data",
      "affectedPersonas": ["persona1", "persona2"],
      "source": "Source and year"
    }}
  ],
  "workshopAngles": [
    {{
      "hmw": "How might we [action] to [outcome]",
      "rationale": "Why this angle matters for {client}",
      "expectedOutcome": "Measurable outcome if solved"
    }}
  ],
  "keyStatistics": [
    {{
      "statistic": "Specific quantified stat",
      "context": "What this means for {biz_fn}",
      "source": "Source and year"
    }}
  ],
  "references": ["Full citation 1", "Full citation 2"]
}}"""

    raw = _call_llm(prompt, max_tokens=8000)
    parsed = _extract_json_object(raw)
    if parsed:
        return parsed
    print("[PDA] JSON formatting failed. Building from raw text...")
    return {
        "executiveSummary": raw_text[:600],
        "marketTrends": [{"title": "See full research", "description": raw_text[:300],
                          "impactLevel": "High", "timeframe": "Short-term", "source": "Research output"}],
        "competitorMoves": [],
        "industryPainPoints": [],
        "workshopAngles": [],
        "keyStatistics": [],
        "references": [],
    }


def _call_research_llm_direct(intake: dict) -> dict:
    """Direct LLM fallback for Stage 1 when one_shot/P&C fails."""
    biz_fn = intake["business_function"]
    client = intake["client_name"]
    industry = intake["industry"]
    sub = intake["sub_industry"]
    keywords = intake["problem_keywords"]
    context = intake["client_context"]

    prompt = f"""\
You are an expert product discovery researcher. Generate comprehensive, deeply detailed \
market research for the following engagement.

CLIENT: {client}
INDUSTRY: {industry} / {sub}
BUSINESS FUNCTION: {biz_fn}
DISCOVERY TYPE: {intake['discovery_type']}
PROBLEM KEYWORDS: {keywords}
CLIENT CONTEXT: {context}

CRITICAL: Every data point must cite a real, named source.
CRITICAL: Each array must have the exact minimum number of items specified.

Return ONLY valid JSON:
{{
  "executiveSummary": "4-5 sentence executive summary with key market insights",
  "marketTrends": [
    {{
      "title": "Specific trend title",
      "description": "2-3 sentences. Must include at least one real statistic (e.g. market size, CAGR, adoption rate) from a named source",
      "impactLevel": "High|Medium|Low",
      "timeframe": "Short-term (0-12 months)|Medium-term (1-3 years)|Long-term (3+ years)",
      "source": "Source name, year (e.g. Gartner 2024, McKinsey 2025)"
    }}
  ],
  "competitorMoves": [
    {{
      "company": "Real company name operating in {industry}",
      "action": "Specific documented action or announcement",
      "implication": "Strategic implication for {client}",
      "source": "Source and year"
    }}
  ],
  "industryPainPoints": [
    {{
      "pain": "Specific pain point title",
      "severity": "Critical|High|Medium",
      "description": "2 sentences with quantified cost, time, or efficiency impact",
      "affectedPersonas": ["Role 1", "Role 2"],
      "source": "Source and year"
    }}
  ],
  "workshopAngles": [
    {{
      "hmw": "How might we [specific action] to [specific measurable outcome] for {client}",
      "rationale": "1-2 sentences: why this angle is most valuable right now",
      "expectedOutcome": "Specific measurable outcome (revenue, efficiency, experience)"
    }}
  ],
  "keyStatistics": [
    {{
      "statistic": "Exact quantified statistic (e.g. '$X billion market by 20XX')",
      "context": "Why this matters for {biz_fn}",
      "source": "Source and year"
    }}
  ],
  "references": [
    "Author/Org. (Year). 'Report Title'. Publisher. URL or publication."
  ]
}}

MINIMUM COUNTS (failure to meet = INVALID response):
- marketTrends: 8 items
- competitorMoves: 6 items
- industryPainPoints: 8 items  
- workshopAngles: 6 items
- keyStatistics: 6 items
- references: 7 items"""

    raw = _call_llm(prompt, _SYSTEM_STRATEGIST, max_tokens=12000)
    return _extract_json_object(raw) or {
        "executiveSummary": f"Market research for {client} in {industry}.",
        "marketTrends": [], "competitorMoves": [], "industryPainPoints": [],
        "workshopAngles": [], "keyStatistics": [], "references": [],
    }


# =============================================================================
# Public router-callable functions for Stage 1
# =============================================================================

def build_research_pc_kwargs(
    shared_state: dict,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover() — Stage 1 P&C mode."""
    from cmbagent.task_framework.prompts.pda.research import (
        research_planner_prompt,
        research_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir
    import datetime

    intake = _get_intake(shared_state)
    cfg = {**_get_research_defaults(), **(config_overrides or {})}
    research_dir = create_work_dir(work_dir, "research_pc")
    year = str(datetime.datetime.now().year)
    fmt_kwargs = dict(year=year, **intake)

    task_desc = (
        f"Conduct comprehensive product discovery market research for "
        f"{intake['client_name']} in {intake['industry']}"
        + (f" / {intake['sub_industry']}" if intake.get("sub_industry") else "")
        + f". Business function: {intake['business_function']}. "
        f"Discovery: {intake['discovery_type']}. "
        f"Keywords: {intake['problem_keywords']}. "
        f"Context: {intake['client_context']}. "
        f"Find 8+ market trends, 7+ pain points, 6+ competitor moves with real sources ({year})."
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=6,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=research_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=research_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(research_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="pda_research",
        callbacks=callbacks,
    )


def extract_research_from_pc_results(results: dict, shared_state: dict) -> dict:
    """Extract and structure research data from planning_and_control results."""
    from cmbagent.task_framework.utils import get_task_result, extract_clean_markdown

    intake = _get_intake(shared_state)
    chat_history = results.get("chat_history", [])
    raw_text = ""

    for agent_name in ("researcher", "researcher_response_formatter"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                raw_text = candidate
                break
        except (ValueError, Exception):
            continue

    if not raw_text:
        logger.warning("[PDA] P&C extraction: scanning all messages")
        best = ""
        for msg in chat_history:
            c = msg.get("content", "")
            if c and isinstance(c, str) and len(c) > len(best):
                best = c
        raw_text = best

    if not raw_text:
        logger.warning("[PDA] P&C: no output, falling back to direct LLM")
        parsed = _call_research_llm_direct(intake)
    else:
        raw_text = extract_clean_markdown(raw_text)
        print(f"[PDA] P&C output: {len(raw_text)} chars. Formatting...")
        parsed = _format_research_as_json(raw_text, intake)

    content_str = _research_summary_to_md(parsed, intake)
    return {"structured": parsed, "content_str": content_str}


def run_research_one_shot(
    shared_state: dict,
    work_dir: str,
    api_keys: dict | None = None,
    callbacks=None,
) -> dict:
    """Stage 1 research via cmbagent.one_shot — default research mode."""
    intake = _get_intake(shared_state)
    print("[PDA] Stage 1: Market Research — launching one_shot researcher...")

    task_desc = (
        f"You are an expert product discovery researcher. Conduct DEEP, comprehensive market "
        f"research with REAL SOURCES for:\n\n"
        f"Client: {intake['client_name']}\n"
        f"Industry: {intake['industry']} / {intake['sub_industry']}\n"
        f"Business Function: {intake['business_function']}\n"
        f"Discovery Type: {intake['discovery_type']}\n"
        f"Problem Keywords: {intake['problem_keywords']}\n"
        f"Context: {intake['client_context']}\n\n"
        f"Research and return DETAILED findings for ALL of the following:\n"
        f"1. EXACTLY 8 current market trends with specific statistics, CAGR, market sizes\n"
        f"2. EXACTLY 7 competitor moves / industry disruptions (real companies, specific actions)\n"
        f"3. EXACTLY 8 quantified industry pain points in {intake['business_function']}\n"
        f"4. EXACTLY 6 HMW (How Might We) workshop angles with rationale\n"
        f"5. EXACTLY 6 key market statistics with sources\n"
        f"6. EXACTLY 8 full references with author, publication, year\n\n"
        f"CRITICAL: Only cite real, verifiable sources. Every claim needs a source."
    )

    raw_text = _call_one_shot_researcher(task_desc, work_dir, api_keys=api_keys)

    if raw_text:
        print(f"[PDA] Researcher output: {len(raw_text)} chars. Structuring...")
        parsed = _format_research_as_json(raw_text, intake)
    else:
        print("[PDA] one_shot empty — using direct LLM...")
        parsed = _call_research_llm_direct(intake)

    content_str = _research_summary_to_md(parsed, intake)
    return {"structured": parsed, "content_str": content_str}


# ---------------------------------------------------------------------------
# Stage 2 — Problem Definition
# ---------------------------------------------------------------------------

def _stage_problem_definition(ss: dict, work_dir: str) -> dict:
    intake = _get_intake(ss)
    research = ss.get("research_summary", {})
    research_str = json.dumps(research, indent=2)[:4000] if isinstance(research, dict) else str(research)[:2000]
    print("[PDA] Stage 2: Problem Definition...")

    existing_section = (
        f"\nExisting Functionality:\n{intake['existing_functionality']}\n"
        if intake["existing_functionality"] else ""
    )

    prompt = f"""\
Generate a COMPREHENSIVE, consultant-quality problem definition for the following engagement.
Every field must be deeply researched, evidence-backed, and practically actionable.

CLIENT: {intake['client_name']}
INDUSTRY: {intake['industry']} / {intake['sub_industry']}
BUSINESS FUNCTION: {intake['business_function']}
DISCOVERY TYPE: {intake['discovery_type']}
PROBLEM KEYWORDS: {intake['problem_keywords']}
PROCESS TYPE: {intake['process_type']}{existing_section}

MARKET RESEARCH CONTEXT:
{research_str}

MINIMUM COUNTS (MUST meet all):
- supportingPoints: 7-8 items (each with specific data evidence)
- personasAffected: 4-5 items (with detailed challenges)
- kpisImpacted: 6-7 items (with current baseline AND target)
- contributingFactors in rootCauseAnalysis: 6-7 items
- reframingExamples: 6-7 items (actionable HMW statements)
- references: 5-6 items

Return ONLY valid JSON:
{{
  "problemStatement": "Clear, evidence-backed 3-4 sentence problem statement. Include quantified business impact.",
  "problemSeverity": "Critical|High|Medium",
  "businessImpact": "Specific quantified financial or operational impact (e.g. '$Xm annual revenue leakage', 'X% productivity loss')",
  "executiveSummary": "2-3 sentence executive-level summary suitable for C-suite presentation",
  "supportingPoints": [
    {{
      "point": "Specific supporting evidence point",
      "dataEvidence": "Quantified data or statistic backing this point",
      "source": "Source name and year",
      "businessImpact": "Specific impact on {intake['client_name']}"
    }}
  ],
  "personasAffected": [
    {{
      "role": "Job title / persona name",
      "grade": "C-suite|VP|Director|Manager|Individual Contributor",
      "painLevel": "Critical|High|Medium",
      "dailyChallenges": ["specific challenge 1", "specific challenge 2", "specific challenge 3"],
      "currentWorkaround": "What they currently do to cope",
      "timeWasted": "Estimated time lost per week/month",
      "frustrationQuote": "Representative quote this persona might say"
    }}
  ],
  "kpisImpacted": [
    {{
      "metric": "Specific KPI name",
      "currentBaseline": "Current measured or estimated value",
      "targetImprovement": "Expected improvement post-solution",
      "businessValue": "Why this KPI matters strategically",
      "measurementMethod": "How this KPI is or should be measured",
      "owner": "Who owns this KPI (role)"
    }}
  ],
  "rootCauseAnalysis": {{
    "primaryCause": "The single most impactful root cause",
    "contributingFactors": [
      {{
        "factor": "Contributing factor",
        "category": "Process|Technology|People|Data|Governance",
        "impact": "How this factor amplifies the problem"
      }}
    ],
    "systemicIssues": "2-3 sentences on systemic or structural issues preventing resolution",
    "urgencyDrivers": ["Why solving this is urgent now (market/regulatory/competitive pressure)"]
  }},
  "reframingExamples": [
    {{
      "hmw": "How might we [specific action verb] [specific object] to [measurable outcome]",
      "opportunity": "The specific opportunity space this opens",
      "successIndicator": "Measurable indicator of success",
      "relevantStage": "Which discovery stage this angle is most relevant to"
    }}
  ],
  "competitiveContext": "2-3 sentences on what competitors are doing about this problem",
  "regulatoryConsiderations": "Any compliance, regulatory, or governance factors relevant to this problem",
  "references": ["Full citation 1", "Full citation 2"]
}}"""

    raw = _call_llm(prompt, _SYSTEM_STRATEGIST, max_tokens=12000)
    parsed = _extract_json_object(raw) or {}
    return {"structured": parsed, "content_str": _problem_definition_to_md(parsed, intake)}


# ---------------------------------------------------------------------------
# Stage 3 — Opportunity Areas
# ---------------------------------------------------------------------------

def _stage_opportunities(ss: dict, work_dir: str) -> dict:
    intake = _get_intake(ss)
    problem = ss.get("problem_definition", {})
    research = ss.get("research_summary", {})
    problem_stmt = problem.get("problemStatement", "") if isinstance(problem, dict) else str(problem)
    business_impact = problem.get("businessImpact", "") if isinstance(problem, dict) else ""
    trends_str = ""
    if isinstance(research, dict) and research.get("marketTrends"):
        trends_str = "\n".join(
            f"- {t.get('title', t) if isinstance(t, dict) else t}"
            for t in research["marketTrends"][:5]
        )
    print("[PDA] Stage 3: Opportunities...")

    prompt = f"""\
Generate 6-7 DISTINCT, deeply-researched, actionable opportunity areas for product discovery.
Each opportunity must be specific, measurable, and directly addressable.

CLIENT: {intake['client_name']}
INDUSTRY: {intake['industry']} / {intake['sub_industry']}
BUSINESS FUNCTION: {intake['business_function']}
DISCOVERY TYPE: {intake['discovery_type']}
PROBLEM STATEMENT: {problem_stmt}
BUSINESS IMPACT: {business_impact}
PROBLEM KEYWORDS: {intake['problem_keywords']}

KEY MARKET TRENDS:
{trends_str}

MINIMUM REQUIREMENTS:
- EXACTLY 6-7 opportunity objects in the array
- Each opportunity: 4-5 KPIs with specific expected improvements
- Each opportunity: at least 2 success stories from real companies
- Each opportunity: implementation complexity rating with rationale

Return ONLY a valid JSON ARRAY:
[
  {{
    "id": "opp-1",
    "title": "Specific, memorable opportunity title (5-8 words)",
    "tagline": "One-sentence hook for executive audiences",
    "explanation": "3-4 sentences: what this opportunity is, why it matters, and what makes it unique",
    "strategicFit": "Why this directly addresses {intake['client_name']}'s stated priorities",
    "valueCategory": "Revenue Growth|Cost Efficiency|Customer Experience|Risk Reduction|Compliance|Innovation",
    "estimatedValue": "Rough ROI estimate with basis (e.g. '$2-5M annual savings based on X% efficiency gain')",
    "kpis": [
      {{
        "metric": "Specific KPI",
        "currentState": "Estimated or benchmarked current value",
        "expectedImprovement": "Specific % or absolute target",
        "timeframe": "X months to achieve",
        "source": "Benchmark source"
      }}
    ],
    "whyNow": "2-3 sentences: market timing, regulatory pressure, or competitive urgency",
    "competitiveAdvantage": "What first-mover advantage this creates for {intake['client_name']}",
    "implementationComplexity": "High|Medium|Low",
    "complexityRationale": "Why this complexity rating (key technical or change management challenges)",
    "timeToFirstValue": "Months to first measurable outcome",
    "timeToFullValue": "Months to full ROI realization",
    "successStories": [
      "Company X (industry) achieved Y% improvement in Z by implementing similar solution (source, year)",
      "Company A achieved $Xm savings through B approach in C industry (source, year)"
    ],
    "risks": ["Key risk 1 with mitigation", "Key risk 2 with mitigation"],
    "dependencies": ["Required capability or prerequisite 1", "Required capability 2"]
  }}
]"""

    raw = _call_llm(prompt, _SYSTEM_STRATEGIST, max_tokens=16000)
    parsed = _extract_json_array_robust(raw)
    if parsed:
        content_str = _opportunities_to_md(parsed)
    else:
        print("[PDA] Stage 3: JSON parse FAILED — storing raw LLM response as fallback")
        parsed = []
        content_str = (
            "# Opportunity Areas\n\n"
            "> ⚠️ Could not parse structured opportunities. Raw output below. Re-run to try again.\n\n"
            "---\n\n" + raw
        )
    return {"structured": parsed, "content_str": content_str}


# ---------------------------------------------------------------------------
# Stage 4 — Solution Archetypes
# ---------------------------------------------------------------------------

def _stage_solution_archetypes(ss: dict, work_dir: str) -> dict:
    intake = _get_intake(ss)
    selected_opp = ss.get("selected_opportunity") or {}
    if isinstance(selected_opp, str):
        try:
            selected_opp = json.loads(selected_opp)
        except (json.JSONDecodeError, TypeError):
            selected_opp = {"title": selected_opp}
    if not isinstance(selected_opp, dict):
        selected_opp = {}
    opp_str = json.dumps(selected_opp, indent=2)[:3000]
    problem = ss.get("problem_definition") or {}
    personas = problem.get("personasAffected", []) if isinstance(problem, dict) else []
    personas_str = json.dumps(personas[:3], indent=2) if personas else "[]"
    print("[PDA] Stage 4: Solution Archetypes...")

    prompt = f"""\
Generate 4-5 DISTINCT, deeply-detailed solution archetypes for the selected opportunity.
Each archetype must represent a fundamentally different technical/business approach.

CLIENT: {intake['client_name']}
INDUSTRY: {intake['industry']}
BUSINESS FUNCTION: {intake['business_function']}

SELECTED OPPORTUNITY:
{opp_str}

KEY PERSONAS:
{personas_str}

MINIMUM REQUIREMENTS:
- EXACTLY 4-5 archetype objects
- Each: 7-8 benefits with measurable outcomes
- Each: specific technology stack
- Each: detailed MVP scope
- Each: realistic risk assessment

Return ONLY a valid JSON ARRAY:
[
  {{
    "id": "arch-1",
    "title": "Solution archetype name (e.g. 'AI-Powered Decision Intelligence Platform')",
    "tagline": "One-sentence value proposition",
    "summary": "3-4 sentences: the approach, core technology, user experience, and unique value",
    "approach": "Detailed 2-3 sentence description of the technical and business approach",
    "techStack": [
      {{
        "category": "AI/ML|Data|Frontend|Backend|Integration|Infrastructure",
        "technologies": ["Tech1", "Tech2"],
        "rationale": "Why these technologies for {intake['client_name']}"
      }}
    ],
    "personas": [
      {{
        "role": "Persona role",
        "interaction": "How this persona interacts with the solution",
        "valueDelivered": "Specific value for this persona"
      }}
    ],
    "benefits": [
      {{
        "benefit": "Specific benefit title",
        "description": "2 sentences: how this benefit is delivered and experienced",
        "measurableOutcome": "Quantified target outcome",
        "timeToRealize": "When benefit starts (weeks/months)"
      }}
    ],
    "mvpScope": "Specific list of features/capabilities included in the MVP (bulleted in this string)",
    "phase2Scope": "What gets built in phase 2",
    "implementationRisks": [
      {{
        "risk": "Risk description",
        "probability": "High|Medium|Low",
        "mitigation": "Specific mitigation strategy"
      }}
    ],
    "estimatedTimeline": "X weeks to MVP, Y months to full deployment",
    "estimatedInvestment": "Rough investment range with key cost drivers",
    "differentiators": ["What makes this archetype unique vs other approaches (7-8 items)"],
    "similarImplementations": ["Company/industry that has successfully done something similar"],
    "references": ["Source supporting this archetype's viability"]
  }}
]"""

    # Stage 4 generates large nested JSON — use 16384 (gpt-4o max output)
    raw = _call_llm(prompt, _SYSTEM_STRATEGIST, max_tokens=16000)
    parsed = _extract_json_array_robust(raw)

    if parsed:
        print(f"[PDA] Stage 4: parsed {len(parsed)} archetypes")
        content_str = _archetypes_to_md(parsed)
    else:
        # JSON parsing failed (likely truncation) — store the raw LLM text so
        # the user can at least see the generated content in the UI review panel
        print("[PDA] Stage 4: JSON parse FAILED — storing raw LLM response as fallback")
        parsed = []
        content_str = (
            "# Solution Archetypes\n\n"
            "> ⚠️ The AI response could not be parsed as structured data. "
            "The raw output is shown below. You can **re-run the stage** to try again, "
            "or review the content below and proceed manually.\n\n"
            "---\n\n" + raw
        )

    return {"structured": parsed, "content_str": content_str}


# ---------------------------------------------------------------------------
# Stage 5 — Features
# ---------------------------------------------------------------------------

def _stage_features(ss: dict, work_dir: str) -> dict:
    intake = _get_intake(ss)
    selected_arch = ss.get("selected_archetype") or {}
    selected_opp = ss.get("selected_opportunity") or {}

    for var, val in [("arch", selected_arch), ("opp", selected_opp)]:
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                val = {"title": val}
        if not isinstance(val, dict):
            val = {}
        if var == "arch":
            selected_arch = val
        else:
            selected_opp = val

    problem = ss.get("problem_definition") or {}
    kpis = problem.get("kpisImpacted", []) if isinstance(problem, dict) else []
    kpis_str = json.dumps(kpis[:5], indent=2) if kpis else "[]"
    expected = ", ".join(intake.get("expected_output", []))
    print("[PDA] Stage 5: Features...")

    prompt = f"""\
Generate a COMPREHENSIVE, production-ready feature set for the selected solution archetype.
Each feature must be fully specified with user stories, acceptance criteria, and success metrics.

CLIENT: {intake['client_name']}
INDUSTRY: {intake['industry']}
EXPECTED OUTPUTS: {expected}

SELECTED OPPORTUNITY:
Title: {selected_opp.get("title", "")}
Value: {selected_opp.get("estimatedValue", "")}

SELECTED SOLUTION ARCHETYPE:
Title: {selected_arch.get("title", "")}
Summary: {selected_arch.get("summary", "")}
MVP Scope: {selected_arch.get("mvpScope", "")}

KEY KPIs TO IMPACT:
{kpis_str}

MINIMUM REQUIREMENTS:
- EXACTLY 10-12 features (mix of Core, Enhancement, Innovation)
- Each feature: EXACTLY 3 user stories (different personas)
- Each feature: 4-5 acceptance criteria
- Each feature: 3-4 success metrics with baseline and target
- Each feature: 4-5 functional requirements
- Distribute: ~5 Must, ~4 Should, ~3 Could features

Return ONLY a valid JSON ARRAY:
[
  {{
    "id": "feat-1",
    "name": "Feature Name (clear, user-centric)",
    "description": "3-4 sentences: what it does, how users interact with it, and the business value delivered",
    "strategicGoal": "Which specific strategic objective this feature advances",
    "userStories": [
      "As a [Primary Persona], I want to [specific action] so that [measurable benefit]",
      "As a [Secondary Persona], I want to [specific action] so that [measurable benefit]",
      "As a [Tertiary Persona/Admin], I want to [specific action] so that [measurable benefit]"
    ],
    "acceptanceCriteria": [
      "Given [context], when [action], then [expected result with measurable threshold]",
      "Given [context], when [action], then [expected result with measurable threshold]",
      "Given [context], when [action], then [expected result with measurable threshold]",
      "System must [non-functional requirement — performance/security/accessibility]",
      "Integration with [system] must [specific SLA or data requirement]"
    ],
    "successMetrics": [
      {{
        "metric": "Specific metric name",
        "baseline": "Current measured or estimated baseline",
        "target": "Expected post-launch target",
        "measurementMethod": "How to measure (tool, query, process)",
        "reviewFrequency": "Daily|Weekly|Monthly"
      }}
    ],
    "functionalRequirements": [
      "The system shall [specific capability]",
      "The system shall [specific capability]",
      "The system shall [specific capability]",
      "The system shall [specific capability]",
      "The system shall [specific capability]"
    ],
    "nonFunctionalRequirements": [
      "Performance: [specific SLA]",
      "Security: [specific requirement]",
      "Accessibility: [WCAG level or specific standard]"
    ],
    "integrations": ["System this feature integrates with"],
    "dataDependencies": ["Data source or dataset required"],
    "dependencies": ["Feature ID this depends on"],
    "estimatedEffort": "S (1-2 wks)|M (2-4 wks)|L (1-2 months)|XL (2+ months)",
    "riskLevel": "High|Medium|Low",
    "riskNotes": "Key implementation or adoption risk",
    "bucket": "Core|Enhancement|Innovation",
    "priority": "Must|Should|Could",
    "valueScore": 1-10,
    "effortScore": 1-10,
    "selected": false
  }}
]"""

    raw = _call_llm(prompt, _SYSTEM_STRATEGIST, max_tokens=16000)
    parsed = _extract_json_array_robust(raw)
    if parsed:
        print(f"[PDA] Stage 5: parsed {len(parsed)} features")
        content_str = _features_to_md(parsed)
    else:
        print("[PDA] Stage 5: JSON parse FAILED — storing raw LLM response as fallback")
        parsed = []
        content_str = (
            "# Feature Set\n\n"
            "> ⚠️ Could not parse structured features. Raw output below. Re-run to try again.\n\n"
            "---\n\n" + raw
        )
    return {"structured": parsed, "content_str": content_str}


# ---------------------------------------------------------------------------
# Stage 6 — Builder Prompts
# ---------------------------------------------------------------------------

def _stage_prompts(ss: dict, work_dir: str) -> dict:
    intake = _get_intake(ss)
    selected_opp = ss.get("selected_opportunity") or {}
    selected_arch = ss.get("selected_archetype") or {}
    selected_features = ss.get("selected_features") or []

    for var, val in [("opp", selected_opp), ("arch", selected_arch)]:
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                val = {"title": val}
        if not isinstance(val, dict):
            val = {}
        if var == "opp":
            selected_opp = val
        else:
            selected_arch = val

    features_str = ""
    if selected_features:
        for f in selected_features[:12]:
            if isinstance(f, dict):
                features_str += f"\n- {f.get('name', '')}: {f.get('description', '')[:120]}"
    print("[PDA] Stage 6: Builder Prompts...")

    prompt = f"""\
Generate THREE comprehensive AI builder prompts for rapidly prototyping this product solution.
Each prompt must be detailed enough for an AI builder to produce a working prototype in ONE session.

CLIENT: {intake['client_name']}
INDUSTRY: {intake['industry']}
OPPORTUNITY: {selected_opp.get('title', '')}
OPPORTUNITY DETAIL: {selected_opp.get('explanation', '')}
SOLUTION: {selected_arch.get('title', '')}
TECHNICAL APPROACH: {selected_arch.get('approach', '')}
TECH STACK: {', '.join(str(t) for t in selected_arch.get('techStack', [])[:3])}

CORE FEATURES:
{features_str}

Return ONLY valid JSON (no markdown fences):
{{
  "lovable": "LOVABLE.DEV PROMPT (700-1000 words):\\n\\nApp Name: [name]\\n\\nYou are building [name] — [one-line description].\\n\\nUSER PERSONAS:\\n[3 detailed persona descriptions with goals and pain points]\\n\\nCORE SCREENS (build all of these):\\n1. [Screen 1]: [detailed UI description with specific components, layout, interactions]\\n2. [Screen 2]: [detailed UI description]\\n3. [Screen 3]: [detailed UI description]\\n4. [Screen 4]: [detailed UI description]\\n5. [Screen 5]: [detailed UI description]\\n\\nFEATURES TO IMPLEMENT (all must work):\\n[Each selected feature with specific UI/UX and interaction details]\\n\\nDESIGN SYSTEM:\\n- Colour palette: [specific hex codes]\\n- Typography: [specific fonts]\\n- Component style: [design language]\\n\\nTECH STACK: [specific technologies]\\n\\nSPECIAL REQUIREMENTS:\\n[integrations, data flows, AI capabilities, real-time features]\\n\\nDELIVERABLE: A fully functional prototype with real data flows, not a static mockup.",
  "bolt": "BOLT.NEW / STACKBLITZ PROMPT (600-800 words):\\n\\nBuild [app name] — [description].\\n\\nTECH STACK: [specific stack with exact versions]\\n\\nARCHITECTURE:\\n[Component structure, state management, data flow]\\n\\nDATABASE SCHEMA:\\n[Key tables/collections with fields]\\n\\nAPI ENDPOINTS TO BUILD:\\n[Key REST or GraphQL endpoints with payloads]\\n\\nCOMPONENTS TO BUILD:\\n[Each component with props and behaviour]\\n\\nAI/ML INTEGRATION:\\n[Specific AI capabilities, models, prompts]\\n\\nFEATURES:\\n[All selected features with implementation guidance]\\n\\nSECURITY: [auth approach, data protection requirements]",
  "googleAI": "GOOGLE AI STUDIO / GEMINI PROMPT (500-700 words):\\n\\nYou are helping build [app name].\\n\\nCONTEXT: [background on client and problem]\\n\\nAI CAPABILITIES NEEDED:\\n[Specific Gemini/Vertex AI capabilities to implement]\\n\\nKEY AI WORKFLOWS:\\n1. [Workflow 1 with input → processing → output]\\n2. [Workflow 2]\\n3. [Workflow 3]\\n\\nDATA INPUTS AND OUTPUTS:\\n[What data comes in, what the AI produces]\\n\\nPROMPT TEMPLATES:\\n[2-3 specific prompt templates for key AI interactions]\\n\\nINTEGRATION POINTS:\\n[How AI outputs connect to the broader application]",
  "general": "GENERAL COPILOT / LLM PROMPT (400-500 words):\\n\\nProject: [app name]\\n\\nYou are a senior software engineer. Build [description].\\n\\nARCHITECTURE OVERVIEW:\\n[High-level architecture with reasoning]\\n\\nDIRECTORY STRUCTURE:\\n[Key directories and their purpose]\\n\\nKEY IMPLEMENTATION CHALLENGES:\\n[Technical challenges and recommended solutions]\\n\\nSTEP-BY-STEP BUILD PLAN:\\n1. [Step 1 with specific technical details]\\n2. [Step 2]\\n3. [Step 3]\\n4. [Step 4]\\n5. [Step 5]\\n\\nTESTING STRATEGY:\\n[Unit, integration, e2e guidance]"
}}"""

    raw = _call_llm(prompt, _SYSTEM_STRATEGIST, max_tokens=14000)
    parsed = _extract_json_object(raw) or {}
    return {"structured": parsed, "content_str": _prompts_to_md(parsed)}


# ---------------------------------------------------------------------------
# Stage 7 — Slide Content
# ---------------------------------------------------------------------------

def _stage_slide_content(ss: dict, work_dir: str) -> dict:
    intake = _get_intake(ss)
    research = ss.get("research_summary") or {}
    problem = ss.get("problem_definition") or {}
    selected_opp = ss.get("selected_opportunity") or {}
    selected_arch = ss.get("selected_archetype") or {}
    features = ss.get("selected_features") or []

    for var, val in [("opp", selected_opp), ("arch", selected_arch), ("prob", problem)]:
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                val = {}
        if not isinstance(val, dict):
            val = {}
        if var == "opp":
            selected_opp = val
        elif var == "arch":
            selected_arch = val
        else:
            problem = val

    problem_stmt = problem.get("problemStatement", "") if isinstance(problem, dict) else ""
    business_impact = problem.get("businessImpact", "") if isinstance(problem, dict) else ""
    market_trends = research.get("marketTrends", []) if isinstance(research, dict) else []
    key_stats = research.get("keyStatistics", []) if isinstance(research, dict) else []
    feature_list = ""
    for f in (features[:8] if isinstance(features, list) else []):
        if isinstance(f, dict):
            feature_list += f"\n- {f.get('name', '')}: {f.get('description', '')[:100]}"
    trends_bullets = "\n".join(
        f"- {t.get('title', t) if isinstance(t, dict) else t}: {t.get('description', '') if isinstance(t, dict) else ''}"
        for t in market_trends[:6]
    )
    print("[PDA] Stage 7: Slide Content...")

    prompt = f"""\
Create a comprehensive, Executive-MBA-quality slide deck content for a Product Discovery \
presentation to C-suite stakeholders. Each section MUST have 7-8 substantive bullet points.

CLIENT: {intake['client_name']}
INDUSTRY: {intake['industry']} / {intake['sub_industry']}
BUSINESS FUNCTION: {intake['business_function']}
DISCOVERY TYPE: {intake['discovery_type']}
PROBLEM STATEMENT: {problem_stmt}
BUSINESS IMPACT: {business_impact}
OPPORTUNITY: {selected_opp.get('title', '')} — {selected_opp.get('explanation', '')}
SOLUTION: {selected_arch.get('title', '')} — {selected_arch.get('summary', '')}
ESTIMATED VALUE: {selected_opp.get('estimatedValue', '')}
FEATURES:{feature_list}

MARKET CONTEXT:
{trends_bullets}

Generate DETAILED slide content in Markdown. Each ## section = one slide.
REQUIREMENTS:
- Each slide: 7-8 substantive bullet points minimum
- Include speaker notes (> blockquotes) for each slide
- Data-backed: reference real statistics where applicable
- Executive-quality: no vague statements, every point is specific and actionable

## 1. Executive Summary
<!-- 7-8 punchy bullets covering: key problem, market urgency, proposed solution, expected ROI, timeline, risk profile, recommendation -->

## 2. Market Context & Strategic Landscape
<!-- 7-8 bullets: market size, growth rate, top trends, disruptions, competitor positioning, regulatory headwinds -->

## 3. Problem Statement & Business Impact
<!-- 7-8 bullets: precise problem statement, quantified impact, affected stakeholders, current cost of inaction, urgency drivers, root causes -->

## 4. Discovery Insights: Research Findings
<!-- 7-8 bullets: key research findings, pain points with data, personas insights, market gaps, benchmarks -->

## 5. Opportunity Space
<!-- 7-8 bullets: selected opportunity, why now, competitive advantage, first-mover window, strategic alignment, risk/reward profile -->

## 6. Proposed Solution Architecture
<!-- 7-8 bullets: solution overview, technical approach, key differentiators, integration architecture, scalability, security/compliance -->

## 7. Core Feature Set & User Experience
<!-- 7-8 bullets: top Must-have features with user value, UX principles, personas served, accessibility, mobile/web approach, AI capabilities -->

## 8. Implementation Roadmap
<!-- 7-8 bullets: Phase 1 (MVP, X weeks), Phase 2 (scale, X months), Phase 3 (optimize), key milestones, critical path, resource requirements -->

## 9. Investment & ROI Analysis
<!-- 7-8 bullets: investment breakdown, expected ROI, payback period, cost avoidance, revenue uplift, risk-adjusted NPV, funding options -->

## 10. Success Metrics & KPI Dashboard
<!-- 7-8 bullets: primary KPIs with targets, measurement framework, review cadence, success criteria, governance, escalation thresholds -->

## 11. Risk Assessment & Mitigation
<!-- 7-8 bullets: top risks with probability/impact, specific mitigations, contingency plans, dependencies, change management needs -->

## 12. Recommended Next Steps
<!-- 7-8 bullets: immediate actions (next 2 weeks), discovery workshop plan, stakeholder alignment sessions, proof of concept scope, decision timeline -->

Include speaker notes under every slide using > blockquotes.
Make every single bullet point specific, data-backed, and consultant-quality."""

    raw = _call_llm(prompt, _SYSTEM_PRESENTER, max_tokens=16000)
    content_str = raw.strip()
    return {"structured": {"slide_content": content_str}, "content_str": content_str}


# ---------------------------------------------------------------------------
# Markdown converters  (rich, detailed output)
# ---------------------------------------------------------------------------

def _research_summary_to_md(data: dict, intake: dict) -> str:
    client = intake.get("client_name", "")
    industry = intake.get("industry", "")
    lines = [f"# Market Research Summary\n**Client:** {client} | **Industry:** {industry}\n"]

    if data.get("executiveSummary"):
        lines += [f"## Executive Summary\n{data['executiveSummary']}\n"]

    if data.get("keyStatistics"):
        lines.append("## Key Market Statistics")
        for stat in data["keyStatistics"]:
            if isinstance(stat, dict):
                lines.append(f"- **{stat.get('statistic', '')}** — {stat.get('context', '')} *(Source: {stat.get('source', '')})*")
            else:
                lines.append(f"- {stat}")
        lines.append("")

    if data.get("marketTrends"):
        lines.append("## Market Trends")
        for t in data["marketTrends"]:
            if isinstance(t, dict):
                impact = t.get("impactLevel", "")
                src = t.get("source", "")
                lines.append(f"### {t.get('title', '')} `[{impact}]`")
                lines.append(f"{t.get('description', '')}")
                lines.append(f"*Timeframe: {t.get('timeframe', '')} | Source: {src}*\n")
            else:
                lines.append(f"- {t}")
        lines.append("")

    if data.get("competitorMoves"):
        lines.append("## Competitor & Market Intelligence")
        for c in data["competitorMoves"]:
            if isinstance(c, dict):
                lines.append(f"- **{c.get('company', '')}**: {c.get('action', '')} → *{c.get('implication', '')}* *(Source: {c.get('source', '')})*")
            else:
                lines.append(f"- {c}")
        lines.append("")

    if data.get("industryPainPoints"):
        lines.append("## Industry Pain Points")
        for p in data["industryPainPoints"]:
            if isinstance(p, dict):
                sev = p.get("severity", "")
                personas = ", ".join(p.get("affectedPersonas", []))
                lines.append(f"### {p.get('pain', '')} `[{sev}]`")
                lines.append(f"{p.get('description', '')}")
                if personas:
                    lines.append(f"*Affects: {personas}*")
                lines.append(f"*Source: {p.get('source', '')}*\n")
            else:
                lines.append(f"- {p}")
        lines.append("")

    if data.get("workshopAngles"):
        lines.append("## Workshop Angles")
        for w in data["workshopAngles"]:
            if isinstance(w, dict):
                lines.append(f"- **HMW:** {w.get('hmw', '')}")
                lines.append(f"  *Rationale: {w.get('rationale', '')}*")
                lines.append(f"  *Expected Outcome: {w.get('expectedOutcome', '')}*")
            else:
                lines.append(f"- {w}")
        lines.append("")

    if data.get("references"):
        lines.append("## References & Sources")
        for r in data["references"]:
            lines.append(f"- {r}")
    return "\n".join(lines)


def _problem_definition_to_md(data: dict, intake: dict = None) -> str:
    client = (intake or {}).get("client_name", "")
    lines = [f"# Problem Definition{f' — {client}' if client else ''}\n"]
    if data.get("executiveSummary"):
        lines += [f"## Executive Summary\n{data['executiveSummary']}\n"]
    if data.get("problemStatement"):
        lines += [f"## Problem Statement\n> {data['problemStatement']}\n"]
    if data.get("businessImpact"):
        lines += [f"**Business Impact:** {data['businessImpact']}\n"]
    if data.get("competitiveContext"):
        lines += [f"## Competitive Context\n{data['competitiveContext']}\n"]
    if data.get("supportingPoints"):
        lines.append("## Supporting Evidence")
        for sp in data["supportingPoints"]:
            if isinstance(sp, dict):
                lines.append(f"- **{sp.get('point', '')}**")
                lines.append(f"  Data: {sp.get('dataEvidence', '')} *(Source: {sp.get('source', '')})*")
                if sp.get("businessImpact"):
                    lines.append(f"  Impact on {client}: {sp['businessImpact']}")
            else:
                lines.append(f"- {sp}")
        lines.append("")
    if data.get("personasAffected"):
        lines.append("## Affected Personas")
        for p in data["personasAffected"]:
            if isinstance(p, dict):
                lines.append(f"### {p.get('role', '')} `[{p.get('painLevel', '')}]`")
                if p.get("grade"):
                    lines.append(f"*Level: {p['grade']}*")
                if p.get("dailyChallenges"):
                    for ch in p["dailyChallenges"]:
                        lines.append(f"- {ch}")
                if p.get("currentWorkaround"):
                    lines.append(f"\n**Current Workaround:** {p['currentWorkaround']}")
                if p.get("timeWasted"):
                    lines.append(f"**Time Lost:** {p['timeWasted']}")
                if p.get("frustrationQuote"):
                    lines.append(f'> "{p["frustrationQuote"]}"')
                lines.append("")
            else:
                lines.append(f"- {p}")
    if data.get("kpisImpacted"):
        lines.append("## KPIs Impacted")
        for k in data["kpisImpacted"]:
            if isinstance(k, dict):
                lines.append(f"- **{k.get('metric', '')}**: {k.get('currentBaseline', '')} → *Target: {k.get('targetImprovement', '')}*")
                lines.append(f"  Strategic value: {k.get('businessValue', '')} | Owner: {k.get('owner', '')}")
            else:
                lines.append(f"- {k}")
        lines.append("")
    if data.get("rootCauseAnalysis"):
        rca = data["rootCauseAnalysis"]
        lines.append("## Root Cause Analysis")
        if isinstance(rca, dict):
            lines.append(f"**Primary Cause:** {rca.get('primaryCause', '')}\n")
            if rca.get("contributingFactors"):
                lines.append("**Contributing Factors:**")
                for cf in rca["contributingFactors"]:
                    if isinstance(cf, dict):
                        lines.append(f"- [{cf.get('category', '')}] **{cf.get('factor', '')}** — {cf.get('impact', '')}")
                    else:
                        lines.append(f"- {cf}")
            if rca.get("systemicIssues"):
                lines.append(f"\n**Systemic Issues:** {rca['systemicIssues']}")
        lines.append("")
    if data.get("reframingExamples"):
        lines.append("## HMW Reframing")
        for r in data["reframingExamples"]:
            if isinstance(r, dict):
                lines.append(f"- **{r.get('hmw', '')}**")
                lines.append(f"  Opportunity: {r.get('opportunity', '')}")
                lines.append(f"  Success Indicator: {r.get('successIndicator', '')}")
            else:
                lines.append(f"- {r}")
        lines.append("")
    if data.get("references"):
        lines.append("## References")
        for ref in data["references"]:
            lines.append(f"- {ref}")
    return "\n".join(lines)


def _opportunities_to_md(data: list) -> str:
    lines = ["# Opportunity Areas\n"]
    for i, opp in enumerate(data, 1):
        if not isinstance(opp, dict):
            lines.append(f"- {opp}")
            continue
        lines.append(f"## {i}. {opp.get('title', 'Opportunity')} `[{opp.get('valueCategory', '')}]`")
        if opp.get("tagline"):
            lines.append(f"*{opp['tagline']}*\n")
        if opp.get("explanation"):
            lines.append(f"{opp['explanation']}\n")
        if opp.get("estimatedValue"):
            lines.append(f"**Estimated Value:** {opp['estimatedValue']}")
        if opp.get("timeToFirstValue"):
            lines.append(f"**Time to First Value:** {opp['timeToFirstValue']}")
        if opp.get("implementationComplexity"):
            lines.append(f"**Complexity:** {opp['implementationComplexity']} — {opp.get('complexityRationale', '')}\n")
        if opp.get("kpis"):
            lines.append("**KPIs:**")
            for k in opp["kpis"]:
                if isinstance(k, dict):
                    lines.append(f"- {k.get('metric', '')}: {k.get('currentState', '')} → {k.get('expectedImprovement', '')} ({k.get('timeframe', '')})")
                else:
                    lines.append(f"- {k}")
        if opp.get("whyNow"):
            lines.append(f"\n**Why Now:** {opp['whyNow']}")
        if opp.get("competitiveAdvantage"):
            lines.append(f"\n**Competitive Advantage:** {opp['competitiveAdvantage']}")
        if opp.get("successStories"):
            lines.append("\n**Success Stories:**")
            for ss in opp["successStories"]:
                lines.append(f"- {ss}")
        if opp.get("risks"):
            lines.append("\n**Risks & Mitigations:**")
            for r in opp["risks"]:
                lines.append(f"- {r}")
        lines.append("")
    return "\n".join(lines)


def _archetypes_to_md(data: list) -> str:
    lines = ["# Solution Archetypes\n"]
    for i, arch in enumerate(data, 1):
        if not isinstance(arch, dict):
            lines.append(f"- {arch}")
            continue
        lines.append(f"## {i}. {arch.get('title', 'Archetype')}")
        if arch.get("tagline"):
            lines.append(f"*{arch['tagline']}*\n")
        if arch.get("summary"):
            lines.append(f"{arch['summary']}\n")
        if arch.get("approach"):
            lines.append(f"**Technical Approach:** {arch['approach']}\n")
        if arch.get("estimatedTimeline"):
            lines.append(f"**Timeline:** {arch['estimatedTimeline']}")
        if arch.get("estimatedInvestment"):
            lines.append(f"**Investment:** {arch['estimatedInvestment']}\n")
        if arch.get("benefits"):
            lines.append("**Benefits:**")
            for b in arch["benefits"]:
                if isinstance(b, dict):
                    lines.append(f"- **{b.get('benefit', '')}**: {b.get('description', '')} *({b.get('measurableOutcome', '')})*")
                else:
                    lines.append(f"- {b}")
        if arch.get("techStack"):
            lines.append("\n**Technology Stack:**")
            for t in arch["techStack"]:
                if isinstance(t, dict):
                    lines.append(f"- **{t.get('category', '')}**: {', '.join(t.get('technologies', []))}")
                else:
                    lines.append(f"- {t}")
        if arch.get("differentiators"):
            lines.append("\n**Differentiators:**")
            for d in arch["differentiators"]:
                lines.append(f"- {d}")
        if arch.get("implementationRisks"):
            lines.append("\n**Implementation Risks:**")
            for r in arch["implementationRisks"]:
                if isinstance(r, dict):
                    lines.append(f"- [{r.get('probability', '')}] **{r.get('risk', '')}** — {r.get('mitigation', '')}")
                else:
                    lines.append(f"- {r}")
        lines.append("")
    return "\n".join(lines)


def _features_to_md(data: list) -> str:
    lines = ["# Feature Set\n"]
    for feat in data:
        if not isinstance(feat, dict):
            lines.append(f"- {feat}")
            continue
        priority = feat.get("priority", "Should")
        bucket = feat.get("bucket", "")
        effort = feat.get("estimatedEffort", "")
        lines.append(f"## {feat.get('name', 'Feature')} `[{priority}]` `[{bucket}]` `[{effort}]`")
        if feat.get("description"):
            lines.append(f"\n{feat['description']}\n")
        if feat.get("strategicGoal"):
            lines.append(f"**Strategic Goal:** {feat['strategicGoal']}\n")
        if feat.get("userStories"):
            lines.append("**User Stories:**")
            for us in feat["userStories"]:
                lines.append(f"- {us}")
        if feat.get("acceptanceCriteria"):
            lines.append("\n**Acceptance Criteria:**")
            for ac in feat["acceptanceCriteria"]:
                lines.append(f"- {ac}")
        if feat.get("successMetrics"):
            lines.append("\n**Success Metrics:**")
            for sm in feat["successMetrics"]:
                if isinstance(sm, dict):
                    lines.append(f"- **{sm.get('metric', '')}**: {sm.get('baseline', '')} → {sm.get('target', '')} (measured via {sm.get('measurementMethod', '')})")
                else:
                    lines.append(f"- {sm}")
        if feat.get("functionalRequirements"):
            lines.append("\n**Functional Requirements:**")
            for fr in feat["functionalRequirements"]:
                lines.append(f"- {fr}")
        lines.append("")
    return "\n".join(lines)


def _prompts_to_md(data: dict) -> str:
    lines = ["# AI Builder Prompts\n"]
    for key, label in [
        ("lovable", "Lovable.dev Prompt"),
        ("bolt", "Bolt.new / StackBlitz Prompt"),
        ("googleAI", "Google AI Studio / Gemini Prompt"),
        ("general", "General Copilot / LLM Prompt"),
    ]:
        if data.get(key):
            lines.append(f"## {label}\n")
            lines.append(data[key])
            lines.append("")
    return "\n".join(lines)
