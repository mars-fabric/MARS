"""
PDA (Product Discovery Assistant) Service.

Replaces the direct Infosys LLM API calls with cmbagent-powered generation.
All LLM calls go through cmbagent's provider infrastructure which auto-detects
OpenAI / Azure / Anthropic / Gemini from environment variables.

Primary strategy for research steps: cmbagent.one_shot(agent='researcher')
for web-search-augmented research, with fallback to direct LLM via
create_openai_client() for structured JSON generation.

Other steps (problem definition, opportunities, etc.) use create_openai_client()
directly for reliable structured JSON generation.
"""

import asyncio
import json
import logging
import os
import re
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Thread pool for running synchronous cmbagent calls
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pda-worker")

# Max retries for direct LLM calls
_MAX_LLM_RETRIES = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_default_model() -> str:
    """Get the default model from cmbagent configuration."""
    try:
        from cmbagent.llm_provider import get_provider_config
        config = get_provider_config()
        if config.is_azure:
            return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        return os.getenv("CMBAGENT_DEFAULT_MODEL", "gpt-4o")
    except Exception:
        return "gpt-4o"


def _clean_json_response(content: str) -> str:
    """Strip markdown fences and extract JSON from LLM response."""
    text = content.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def _extract_json_object(text: str) -> Optional[dict]:
    """Extract the first JSON object {...} from text, handling nested braces."""
    if not text:
        return None
    cleaned = _clean_json_response(text)

    # Try direct parse first (fastest path)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Find balanced braces
    start = cleaned.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i + 1])
                except json.JSONDecodeError:
                    break
    # Fallback: greedy regex
    m = re.search(r'\{[\s\S]*\}', cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_array(text: str) -> Optional[list]:
    """Extract the first JSON array [...] from text."""
    if not text:
        return None
    cleaned = _clean_json_response(text)

    # Try direct parse first
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass

    m = re.search(r'\[[\s\S]*\]', cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Core LLM call via cmbagent's provider infrastructure
# ---------------------------------------------------------------------------

def _call_llm_direct(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 12000,
) -> str:
    """
    Call LLM directly using cmbagent's create_openai_client().
    This uses the same provider auto-detection (OpenAI/Azure/etc.)
    that cmbagent uses internally.  Retries on transient failures.
    """
    from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider

    client = create_openai_client()
    model = resolve_model_for_provider(_get_default_model())

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_err: Optional[Exception] = None
    for attempt in range(1, _MAX_LLM_RETRIES + 1):
        try:
            logger.info(
                "PDA LLM call [attempt %d/%d]: model=%s, prompt_len=%d",
                attempt, _MAX_LLM_RETRIES, model, len(prompt),
            )
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            logger.info("PDA LLM response: len=%d", len(content))
            return content
        except Exception as e:
            last_err = e
            logger.warning("PDA LLM attempt %d failed: %s", attempt, e)
            if attempt < _MAX_LLM_RETRIES:
                import time
                time.sleep(1 * attempt)  # simple back-off

    raise RuntimeError(f"PDA LLM call failed after {_MAX_LLM_RETRIES} attempts: {last_err}")


def _call_cmbagent_researcher(task: str, work_dir: Optional[str] = None) -> Optional[str]:
    """
    Use cmbagent.one_shot with researcher agent for research-heavy tasks.
    Returns the extracted text content, or None if the call fails.

    Callers should have a fallback to _call_llm_direct for robustness.
    """
    try:
        import cmbagent
        from cmbagent.utils import get_api_keys_from_env
    except ImportError as e:
        logger.warning("cmbagent not available for researcher: %s", e)
        return None

    if work_dir is None:
        work_dir = os.path.expanduser(
            os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
        )

    run_dir = os.path.join(work_dir, "pda_runs", f"pda_{uuid.uuid4().hex[:8]}")
    os.makedirs(run_dir, exist_ok=True)

    api_keys = get_api_keys_from_env()
    logger.info("PDA researcher one_shot: task_len=%d, work_dir=%s", len(task), run_dir)

    try:
        results = cmbagent.one_shot(
            task=task,
            agent='researcher',
            max_rounds=15,
            max_n_attempts=2,
            work_dir=run_dir,
            api_keys=api_keys,
            clear_work_dir=False,
        )
    except Exception as e:
        logger.warning(
            "cmbagent.one_shot(researcher) failed (will fallback to direct LLM): %s\n%s",
            e, traceback.format_exc(),
        )
        # Try to salvage output from run directory
        salvaged = _salvage_researcher_output(run_dir)
        if salvaged:
            logger.info("Salvaged researcher output from run_dir (%d chars)", len(salvaged))
            return salvaged
        return None

    # Extract the researcher's actual output from chat history.
    # In autogen GroupChat, agent text messages have role='user' (not 'assistant')
    # and the agent name is in the 'name' field. We look for messages from
    # 'researcher' by name, preferring earlier (first-attempt) responses.
    chat_history = results.get('chat_history', [])

    # Collect candidate messages from the researcher agent
    researcher_outputs = []
    for msg in chat_history:
        if not isinstance(msg, dict):
            continue
        name = msg.get('name', '')
        content = msg.get('content', '')
        if not content or content == 'None':
            continue
        # Skip failure/retry boilerplate
        if isinstance(content, str) and any(phrase in content.lower() for phrase in [
            'has been marked as failed',
            'exitcode: 1',
            'execution failed',
            'if further assistance is needed',
        ]):
            continue
        # Accept messages from the researcher or response formatter
        if name in ('researcher', 'researcher_response_formatter'):
            researcher_outputs.append(content)

    # Return the first substantial researcher output (from the first attempt)
    for output in researcher_outputs:
        if isinstance(output, str) and len(output.strip()) > 50:
            return output

    # Fallback: any researcher output at all
    if researcher_outputs:
        return researcher_outputs[0]

    # Fallback: try final_context
    final_ctx = results.get('final_context', {})
    if isinstance(final_ctx, dict):
        for key in ('researcher_output', 'response', 'result', 'content'):
            if key in final_ctx and final_ctx[key]:
                return str(final_ctx[key])

    raw = json.dumps(results.get('final_context', {}))
    return raw if raw and raw != '{}' else None


def _salvage_researcher_output(run_dir: str) -> Optional[str]:
    """
    Try to extract useful output from the researcher's run directory.
    The researcher may have written partial results before crashing.
    """
    try:
        for fname in os.listdir(run_dir):
            if fname.endswith('.json'):
                fpath = os.path.join(run_dir, fname)
                with open(fpath, 'r') as f:
                    content = f.read()
                if content.strip():
                    logger.info("Found researcher output in %s", fpath)
                    return content
            if fname.endswith('.md') or fname.endswith('.txt'):
                fpath = os.path.join(run_dir, fname)
                with open(fpath, 'r') as f:
                    content = f.read()
                if content.strip():
                    logger.info("Found researcher output in %s", fpath)
                    return content
    except Exception as e:
        logger.debug("Could not salvage from run_dir: %s", e)
    return None


def _extract_pc_output(results: Dict[str, Any]) -> Optional[str]:
    """
    Extract usable research text from planning_and_control_context_carryover results.

    The return shape is the same as one_shot: {chat_history, final_context, ...}.
    We try multiple extraction strategies:
      1. final_context['previous_steps_execution_summary'] — concatenated markdown
         of all completed steps (richest output from P&C).
      2. Chat history messages from 'researcher' / 'researcher_response_formatter'.
      3. Any substantial final_context string values.
    """
    if not results or not isinstance(results, dict):
        return None

    # Strategy 1: previous_steps_execution_summary from final_context
    final_ctx = results.get('final_context', {})
    if isinstance(final_ctx, dict):
        summary = final_ctx.get('previous_steps_execution_summary', '')
        if isinstance(summary, str) and len(summary.strip()) > 50:
            logger.info("P&C extract: using previous_steps_execution_summary (%d chars)", len(summary))
            return summary

    # Strategy 2: chat_history messages from researcher agents
    chat_history = results.get('chat_history', [])
    researcher_outputs = []
    for msg in chat_history:
        if not isinstance(msg, dict):
            continue
        name = msg.get('name', '')
        content = msg.get('content', '')
        if not content or content == 'None':
            continue
        if isinstance(content, str) and any(phrase in content.lower() for phrase in [
            'has been marked as failed',
            'exitcode: 1',
            'execution failed',
        ]):
            continue
        if name in ('researcher', 'researcher_response_formatter'):
            researcher_outputs.append(content)

    for output in researcher_outputs:
        if isinstance(output, str) and len(output.strip()) > 50:
            return output
    if researcher_outputs:
        return researcher_outputs[0]

    # Strategy 3: any final_context string values
    if isinstance(final_ctx, dict):
        for key in ('researcher_output', 'response', 'result', 'content', 'output'):
            val = final_ctx.get(key)
            if val and isinstance(val, str) and len(val.strip()) > 20:
                return val

    # Strategy 4: serialize final_context
    raw = json.dumps(final_ctx) if isinstance(final_ctx, dict) else str(final_ctx)
    return raw if raw and raw not in ('{}', 'None', '') else None


def _call_cmbagent_planning_control(task: str, work_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Use cmbagent.planning_and_control_context_carryover for complex multi-step research.
    Returns structured results with plan, steps, and artifacts.
    """
    import cmbagent
    from cmbagent.utils import get_api_keys_from_env

    if work_dir is None:
        work_dir = os.path.expanduser(
            os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
        )

    run_dir = os.path.join(work_dir, "pda_runs", f"pda_pc_{uuid.uuid4().hex[:8]}")
    os.makedirs(run_dir, exist_ok=True)

    api_keys = get_api_keys_from_env()
    logger.info("PDA P&C: task_len=%d, work_dir=%s", len(task), run_dir)

    results = cmbagent.planning_and_control_context_carryover(
        task=task,
        max_rounds_control=25,
        max_n_attempts=3,
        max_plan_steps=3,
        n_plan_reviews=1,
        work_dir=run_dir,
        api_keys=api_keys,
        clear_work_dir=False,
    )
    return results


# ---------------------------------------------------------------------------
# Async wrappers (run sync calls in thread pool)
# ---------------------------------------------------------------------------

async def _async_llm_direct(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 12000,
) -> str:
    loop = asyncio.get_event_loop()
    fn = partial(_call_llm_direct, prompt, system_prompt, temperature, max_tokens)
    return await loop.run_in_executor(_executor, fn)


async def _async_researcher(task: str) -> Optional[str]:
    """Best-effort researcher call.  Returns None on failure."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _call_cmbagent_researcher, task)


async def _async_planning_control(task: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _call_cmbagent_planning_control, task)


# ---------------------------------------------------------------------------
# PDA Step Implementations
# ---------------------------------------------------------------------------

_SYSTEM_STRATEGIST = (
    "You are a senior Product Discovery strategist at Domain Consulting Group. "
    "You specialize in turning fuzzy business problems into clear, evidence-backed "
    "opportunity spaces. CRITICAL RULE: You MUST use ONLY real, verifiable, factual data. "
    "Every statistic, percentage, market size, growth rate, competitor move, and trend you cite "
    "MUST be grounded in real-world sources — publicly available reports (Gartner, McKinsey, "
    "Forrester, Statista, company earnings, SEC filings, industry publications). "
    "NEVER fabricate numbers. If you cite '50% improvement' it must be a real documented case. "
    "If unsure, say 'estimated' or 'industry benchmarks suggest'. Include source references. "
    "Always return ONLY valid JSON — no markdown, no prose."
)


async def get_client_details(client_name: str) -> Dict[str, Any]:
    """
    Step 0 helper: Auto-detect ALL intake fields from company name.
    Uses direct LLM via cmbagent provider.
    Returns industry, sub-industry, client context, business functions,
    suggested discovery types, and problem keywords — all editable by user.
    """
    prompt = f"""You are a business intelligence assistant with deep knowledge of global companies. Based on the client/company name provided, generate a COMPREHENSIVE profile with REAL, FACTUAL information.

Client/Company Name: {client_name}

IMPORTANT: Use ONLY real, verifiable facts about this company. Include actual revenue figures, employee counts, market positions, real product names, real strategic initiatives, and real technology stacks. If the company is well-known, use your factual knowledge. Do NOT make up statistics or initiatives. If uncertain about specific numbers, say "estimated" but stay grounded in reality.

Return ONLY valid JSON with no markdown formatting, using this exact structure:
{{
  "industry": "Primary industry (e.g., Retail, Healthcare, Financial Services, Technology, Manufacturing)",
  "subIndustry": "More specific sub-industry (e.g., Fashion Retail, Investment Banking, Cloud Services)",
  "clientContext": "A detailed 4-6 sentence paragraph about the company using REAL facts: actual revenue/market cap, employee count, market position, key products/services, recent strategic initiatives (with real names), digital maturity level, technology stack they are known to use, and competitive landscape. Use real numbers and real initiative names.",
  "businessFunctions": ["Top 3-5 most relevant business functions from: Store Ops, Supply Chain, Merchandising, E-commerce, HR, Finance, Manufacturing, Marketing, Customer Service, R&D, Data Analytics, IT Operations, Logistics, Sales, Product Management"],
  "suggestedDiscoveryTypes": ["2-3 most relevant discovery types from: Problem, Opportunity, Pain Point, Capability, Open Discovery, Process Optimization, Digital Transformation, Customer Experience, Automation, Innovation"],
  "problemKeywords": "3-5 real, current challenges or opportunities this company is known to face based on recent news, earnings calls, or industry analysis. Be specific and factual.",
  "suggestedBusinessFunctions": ["All applicable business functions for this company type"]
}}"""

    content = await _async_llm_direct(
        prompt,
        "You are a business intelligence assistant specializing in company analysis. "
        "You MUST use real, factual, verifiable information. Never fabricate statistics or initiatives.",
    )

    parsed = _extract_json_object(content)
    if parsed:
        return {
            "industry": parsed.get("industry", ""),
            "subIndustry": parsed.get("subIndustry", ""),
            "clientContext": parsed.get("clientContext", ""),
            "businessFunctions": parsed.get("businessFunctions", []),
            "suggestedDiscoveryTypes": parsed.get("suggestedDiscoveryTypes", []),
            "problemKeywords": parsed.get("problemKeywords", ""),
            "suggestedBusinessFunctions": parsed.get("suggestedBusinessFunctions", []),
        }

    return {
        "industry": "", "subIndustry": "", "clientContext": "",
        "businessFunctions": [], "suggestedDiscoveryTypes": [],
        "problemKeywords": "", "suggestedBusinessFunctions": [],
    }


async def generate_research_summary(intake_data: Dict[str, Any], research_mode: str = "one_shot") -> Dict[str, Any]:
    """
    Step 1: Generate research summary.

    research_mode:
      - "one_shot": cmbagent.one_shot(agent='researcher') — fast, single-agent research.
      - "planning_and_control": cmbagent.planning_and_control_context_carryover()
        — multi-step planning → control deep research.

    Fallback: direct LLM via create_openai_client() if the chosen method fails.
    """
    research_prompt = _build_research_prompt(intake_data)

    researcher_text: Optional[str] = None

    if research_mode == "planning_and_control":
        # --- Primary: use cmbagent planning & control ---
        logger.info("Step 1: attempting cmbagent.planning_and_control_context_carryover()")
        try:
            pc_results = await _async_planning_control(research_prompt)
            researcher_text = _extract_pc_output(pc_results)
            if researcher_text:
                logger.info("Step 1: P&C returned text (%d chars)", len(researcher_text))
        except Exception as e:
            logger.warning(
                "Step 1: planning_and_control failed (will fallback): %s\n%s",
                e, traceback.format_exc(),
            )
    else:
        # --- Primary: use cmbagent researcher agent (one_shot) ---
        logger.info("Step 1: attempting cmbagent.one_shot(researcher)")
        researcher_text = await _async_researcher(research_prompt)

    if researcher_text:
        parsed = _extract_json_object(researcher_text)
        if parsed and _is_valid_research(parsed):
            logger.info("Step 1: researcher returned valid JSON (%d chars)", len(researcher_text))
            return _normalise_research(parsed)

        # Researcher returned text but not valid JSON — try to parse as free text
        logger.info("Step 1: researcher returned text (%d chars) but not structured JSON, "
                     "feeding to LLM for structuring", len(researcher_text))
        structure_prompt = f"""You are given raw research text. Your job is to extract and organize it into the JSON format below.
Do NOT make up new information — only restructure what is provided.

### Raw Research Text
{researcher_text[:15000]}

### Required JSON format (return ONLY valid JSON, no markdown):
{{
  "marketTrends": ["trend 1", "trend 2", ...],
  "competitorMoves": ["move 1", "move 2", ...],
  "industryPainPoints": ["pain 1", "pain 2", ...],
  "workshopAngles": ["angle 1", "angle 2", ...],
  "references": ["ref 1", "ref 2", ...]
}}"""
        try:
            structured = await _async_llm_direct(structure_prompt, _SYSTEM_STRATEGIST, temperature=0.3)
            parsed2 = _extract_json_object(structured)
            if parsed2 and _is_valid_research(parsed2):
                logger.info("Step 1: structured researcher output into valid JSON")
                return _normalise_research(parsed2)
        except Exception as e:
            logger.warning("Step 1: structuring researcher output failed: %s", e)

    # --- Fallback: direct LLM ---
    logger.info("Step 1: falling back to direct LLM for research summary")
    content = await _async_llm_direct(research_prompt, _SYSTEM_STRATEGIST)

    parsed = _extract_json_object(content)
    if parsed and _is_valid_research(parsed):
        logger.info("Step 1: research summary generated via direct LLM fallback")
        return _normalise_research(parsed)

    # Last resort: wrap raw text
    logger.warning("Step 1: could not parse JSON from any source (len=%d)", len(content) if content else 0)
    return {
        "marketTrends": [content] if content else ["Unable to generate research. Please retry."],
        "competitorMoves": [],
        "industryPainPoints": [],
        "workshopAngles": [],
        "references": [],
    }


def _build_research_prompt(intake_data: Dict[str, Any]) -> str:
    """Build the research-summary prompt from intake data."""
    process_info = (
        f"Existing Process - {intake_data.get('existingFunctionality', '')}"
        if intake_data.get('processType') == 'existing'
        else "New Process"
    )
    return f"""You are a senior Product Discovery strategist at Domain Consulting Group, specializing in turning fuzzy business problems into clear, evidence-backed opportunity spaces.

CRITICAL: ALL data, statistics, percentages, market sizes, growth rates, and competitor moves you mention MUST be REAL and VERIFIABLE. Cite real reports (Gartner, McKinsey, Forrester, Statista, IDC, company earnings calls, SEC filings, industry publications). If you say "40% of retailers" or "$4.4 trillion market" — it must be a real documented figure. NEVER fabricate statistics. When uncertain, use "industry estimates suggest" or "analysts project approximately" and cite the source.

Using the inputs below, generate a concise but comprehensive research summary that is tightly focused on the specific Problem/Keywords (do not default to generic industry overviews):

* Client: {intake_data.get('clientName', '')}
* Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
* Client Context: {intake_data.get('clientContext', '')}
* Business Function / Domain: {intake_data.get('businessFunction', '')}
* Discovery Type: {intake_data.get('discoveryType', '')}
* Process Type: {process_info}
* Problem / Keywords (Primary Lens): {intake_data.get('problemKeywords', '')}

### Scope & Focus
1. Anchor everything on the Problem/Keywords and Client Context.
   - Treat the problem keywords as the primary lens.
   - Use the Client Context to tailor all insights.
   - Only include trends, competitors, pain points, and workshop angles that clearly connect to this problem area.
2. Perspective: Domain Consulting Group – Product Discovery.
   - Prioritize insights for opportunity framing, risk identification, value propositions, and solution hypotheses.
3. Level of Detail: Clear, non-fluffy, consulting-style language. Each item should be 2-4 sentences with specific data points, statistics, or examples wherever possible. Be thorough and substantive.
4. **CRITICAL: Provide 10 to 15 points per section. Do NOT provide fewer than 10.** Quantity AND quality matter — cover the space comprehensively.

### Output Format (JSON only)
Return ONLY valid JSON, no markdown, no explanations:
{{
  "marketTrends": ["Each item: a concrete, REAL, data-backed trend related to the Problem/Keywords. Cite specific reports, studies, or publications. Include real numbers (market sizes, growth rates, adoption percentages) from verifiable sources like Gartner, McKinsey, Forrester, Statista, IDC, or company earnings. 2-4 sentences per item. 10-15 items REQUIRED."],
  "competitorMoves": ["Each item: a REAL, documented competitor move or strategic initiative relevant to the Problem/Keywords. Name REAL companies and their ACTUAL announced or reported actions (product launches, acquisitions, partnerships, strategy shifts). Include dates where possible. 2-4 sentences. 10-15 items REQUIRED."],
  "industryPainPoints": ["Each item: a concrete pain point tied to the Problem/Keywords, backed by REAL survey data, research findings, or documented case studies. Include measurable impact with REAL figures (cost, time, revenue, satisfaction scores from actual studies). 2-4 sentences. 10-15 items REQUIRED."],
  "workshopAngles": ["Each item: a sharp, provocative angle for a product discovery workshop grounded in REAL industry evidence. Reference actual case studies, implementations, or research findings. Include the 'so what' — why this angle matters and what it unlocks. 2-4 sentences. 10-15 items REQUIRED."],
  "references": ["Each item: a REAL, specific, authoritative reference (actual report titles with publication years, e.g., 'Gartner Magic Quadrant for Supply Chain Planning Solutions 2024', 'McKinsey Global Institute: The Future of Work 2023'). 8-12 items. ONLY cite references that actually exist."]
}}"""


def _is_valid_research(parsed: dict) -> bool:
    """Check if parsed dict has at least one non-empty research section."""
    for key in ('marketTrends', 'competitorMoves', 'industryPainPoints', 'workshopAngles'):
        val = parsed.get(key, [])
        if isinstance(val, list) and len(val) > 0:
            return True
    return False


def _normalise_research(parsed: dict) -> Dict[str, Any]:
    """Normalise a parsed research dict to the expected shape."""
    def _to_list(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str) and v:
            return [v]
        return []
    return {
        "marketTrends": _to_list(parsed.get("marketTrends")),
        "competitorMoves": _to_list(parsed.get("competitorMoves")),
        "industryPainPoints": _to_list(parsed.get("industryPainPoints")),
        "workshopAngles": _to_list(parsed.get("workshopAngles")),
        "references": _to_list(parsed.get("references")),
    }


async def generate_problem_definition(
    intake_data: Dict[str, Any],
    research_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Step 2: Generate problem definition using direct LLM.
    No web search needed — we already have the research summary.
    """
    market = ", ".join(research_summary.get("marketTrends", []))
    competitors = ", ".join(research_summary.get("competitorMoves", []))
    pains = ", ".join(research_summary.get("industryPainPoints", []))

    process_info = (
        f"Existing Process - {intake_data.get('existingFunctionality', '')}"
        if intake_data.get('processType') == 'existing'
        else "New Process"
    )

    prompt = f"""You are a senior Product Discovery strategist at Domain Consulting Group. Based on the following research and inputs, generate a thorough, evidence-backed problem definition that will anchor the entire product discovery engagement.

CRITICAL: ALL statistics, percentages, cost figures, improvement metrics, and impact assessments MUST be REAL and VERIFIABLE. Reference actual studies, surveys, reports, and documented case studies. When you say a KPI can improve by X%, cite a real benchmark or case study. Never fabricate numbers.

Research Summary:
Market Trends: {market}
Competitor Moves: {competitors}
Pain Points: {pains}

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {process_info}
- Problem Keywords: {intake_data.get('problemKeywords', '')}

### Requirements
- Consider the client's specific context, organizational maturity, competitive landscape, and strategic priorities when framing the problem.
- The problem statement should be sharp, specific, and anchored in evidence from the research summary.
- Supporting points should connect research findings to client-specific impact.
- Root cause analysis should go 3 levels deep (symptom → cause → systemic root cause).
- Personas should include their pain frequency, severity, and workaround cost.
- KPIs should include current baseline estimates and target improvement ranges.
- Reframing examples should unlock new solution spaces.

Return ONLY valid JSON, no prefix or suffix text:
{{
  "problemStatement": "A crisp 2-3 sentence problem statement that is specific to this client and anchored in research evidence",
  "supportingPoints": ["6-8 evidence-backed points connecting research to client impact. Each 2-3 sentences with specific data."],
  "personasAffected": ["6-8 personas with format: 'Persona Name — pain description, frequency, and cost of current workarounds'"],
  "kpisImpacted": ["6-8 KPIs with format: 'KPI Name: current estimated state → target state (% improvement range)'"],
  "rootCause": "Deep 3-level root cause analysis in 3-4 paragraphs. Level 1: visible symptoms. Level 2: operational causes. Level 3: systemic/structural root causes. Include interconnections between causes.",
  "reframingExamples": ["4-6 alternative problem framings that open different solution spaces. Each 2-3 sentences."],
  "impactAssessment": "2-3 paragraphs quantifying the cost of inaction: revenue impact, efficiency loss, competitive risk, and customer impact.",
  "references": ["4-6 specific sources backing the analysis"]
}}"""

    content = await _async_llm_direct(prompt, _SYSTEM_STRATEGIST)

    parsed = _extract_json_object(content)
    if parsed:
        return {
            "problemStatement": parsed.get("problemStatement", ""),
            "supportingPoints": parsed.get("supportingPoints", []),
            "personasAffected": parsed.get("personasAffected", []),
            "kpisImpacted": parsed.get("kpisImpacted", []),
            "rootCause": parsed.get("rootCause", ""),
            "reframingExamples": parsed.get("reframingExamples", []),
            "impactAssessment": parsed.get("impactAssessment", ""),
            "references": parsed.get("references", []),
        }

    return {
        "problemStatement": content if content else "Unable to generate problem definition. Please retry.",
        "supportingPoints": [],
        "personasAffected": [],
        "kpisImpacted": [],
        "rootCause": "",
        "reframingExamples": [],
        "impactAssessment": "",
        "references": [],
    }


async def generate_opportunities(
    intake_data: Dict[str, Any],
    problem_definition: str,
) -> List[Dict[str, Any]]:
    """
    Step 3: Generate opportunity areas.
    Primary: cmbagent.one_shot(researcher) for research-backed opportunities.
    Fallback: direct LLM for structured JSON generation.
    """
    process_info = (
        f"Existing Process - Current functionality: {intake_data.get('existingFunctionality', '')}"
        if intake_data.get('processType') == 'existing'
        else 'New Process'
    )

    prompt = f"""You are a senior Product Discovery strategist at Domain Consulting Group. Based on the problem definition below, generate 6-10 specific, high-value opportunity areas that are tightly connected to the client's problem space.

CRITICAL: ALL data points, improvement percentages, market sizes, ROI figures, and benchmarks MUST be REAL, VERIFIABLE numbers from actual industry reports, case studies, or documented implementations. Cite sources. NEVER fabricate statistics.

Problem Definition:
{problem_definition}

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {process_info}
- Problem Keywords: {intake_data.get('problemKeywords', '')}

### Requirements
- Tailor every opportunity to the client's specific context, organizational capabilities, digital maturity, and strategic priorities.
- Be SPECIFIC: name technologies, methodologies, platforms, or frameworks where relevant.
- Each opportunity should be distinct — avoid overlap. Cover a broad range of value categories.
- For each opportunity, deeply explain the business case: WHY this matters NOW, WHAT changes it drives, and HOW success is measured.
- Provide 6 to 10 opportunity areas. Quality AND quantity matter.

For each opportunity, provide:
1. Title (concise, compelling, action-oriented)
2. Explanation (3-5 sentences: what this opportunity is, why it matters, what it unlocks, and how it connects to the client's problem)
3. Value category (Revenue, Efficiency, Experience, Risk, or Innovation)
4. KPIs influenced (4-6 specific, measurable metrics with target direction — e.g., "Reduce manual processing time by 40-60%")
5. "Why now" justification (2-3 sentences: market timing, technology readiness, competitive pressure)
6. Implementation considerations (2-3 sentences: key enablers, prerequisites, or risks)
7. References (1-2 sources)

Format as JSON array with this structure, no prefix or suffix text:
[
  {{
    "title": "...",
    "explanation": "...",
    "valueCategory": "Revenue|Efficiency|Experience|Risk|Innovation",
    "kpis": ["...", "...", "...", "..."],
    "whyNow": "...",
    "implementationNotes": "...",
    "references": ["..."]
  }}
]"""

    # --- Primary: try cmbagent researcher ---
    logger.info("Step 3: attempting cmbagent.one_shot(researcher) for opportunities")
    researcher_text = await _async_researcher(prompt)

    if researcher_text:
        arr = _extract_json_array(researcher_text)
        if arr and len(arr) >= 2:
            logger.info("Step 3: researcher returned valid JSON array (%d items)", len(arr))
            return [{"id": f"opp-{i}", **opp} for i, opp in enumerate(arr)]

        # Researcher returned text but not structured — feed to LLM for structuring
        logger.info("Step 3: researcher returned text (%d chars), structuring via LLM", len(researcher_text))
        structure_prompt = f"""Extract and organize the following research into the JSON array format below. Do NOT invent new information.

### Raw Research
{researcher_text[:15000]}

### Required format (return ONLY valid JSON array):
[{{"title":"...","explanation":"...","valueCategory":"...","kpis":["..."],"whyNow":"...","implementationNotes":"...","references":["..."]}}]"""
        try:
            structured = await _async_llm_direct(structure_prompt, _SYSTEM_STRATEGIST, temperature=0.3)
            arr2 = _extract_json_array(structured)
            if arr2 and len(arr2) >= 2:
                return [{"id": f"opp-{i}", **opp} for i, opp in enumerate(arr2)]
        except Exception as e:
            logger.warning("Step 3: structuring researcher output failed: %s", e)

    # --- Fallback: direct LLM ---
    logger.info("Step 3: falling back to direct LLM for opportunities")
    content = await _async_llm_direct(prompt, "You are a senior product discovery strategist.")

    arr = _extract_json_array(content)
    if arr:
        return [{"id": f"opp-{i}", **opp} for i, opp in enumerate(arr)]

    return []


async def generate_solution_archetypes(
    selected_opportunity: Dict[str, Any],
    intake_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Step 4: Generate solution archetypes.
    Primary: cmbagent.one_shot(researcher) for research-backed archetypes.
    Fallback: direct LLM for structured JSON generation.
    """
    process_info = (
        f"Existing Process - {intake_data.get('existingFunctionality', '')}"
        if intake_data.get('processType') == 'existing'
        else 'New Process'
    )

    prompt = f"""You are a senior Product Discovery strategist and solution architect at Domain Consulting Group. Based on this opportunity, generate 3-5 distinct solution archetypes that address it from different strategic angles.

CRITICAL: ALL benefits, improvement metrics, cost savings, and performance claims MUST be grounded in REAL industry benchmarks, documented case studies, or verifiable data. When you say "Reduce decision-making time by 60%" — cite a real implementation or benchmark. NEVER fabricate numbers.

Opportunity: {selected_opportunity.get('title', '')}
{selected_opportunity.get('explanation', '')}
Value Category: {selected_opportunity.get('valueCategory', '')}
KPIs: {', '.join(selected_opportunity.get('kpis', []))}

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {process_info}
- Problem Keywords: {intake_data.get('problemKeywords', '')}

### Requirements
- Tailor solution archetypes to the client's digital maturity, organizational capabilities, tech landscape, and strategic priorities.
- Each archetype must be DISTINCT in approach (e.g., AI-powered assistant vs. Predictive analytics engine vs. Automation co-pilot vs. Command center vs. Self-service portal).
- Be SPECIFIC about technologies, AI/ML techniques, integration patterns, and architecture approaches.
- Think about the full user journey — not just features, but how the solution fits into daily workflows.

For each archetype, provide:
1. Title (distinctive and descriptive)
2. Summary (4-6 sentences: what it is, how it works, key differentiator, and value proposition)
3. Core approach (1-2 sentences: the fundamental strategy — e.g., "Uses NLP + knowledge graphs to surface relevant insights proactively")
4. Personas who will use it (3-5 personas with their primary use case)
5. Expected benefits (5-8 specific, measurable benefits — e.g., "Reduce decision-making time from 3 days to 4 hours")
6. Technology enablers (3-5 key technologies or platforms needed)
7. Implementation complexity (Low/Medium/High with 1-2 sentence justification)
8. References (1-2 sources)

Format as JSON array:
[
  {{
    "title": "...",
    "summary": "...",
    "coreApproach": "...",
    "personas": ["Persona: use case", "..."],
    "benefits": ["...", "...", "...", "...", "..."],
    "technologyEnablers": ["...", "...", "..."],
    "implementationComplexity": "Low|Medium|High — explanation",
    "references": ["..."]
  }}
]"""

    # --- Primary: try cmbagent researcher ---
    logger.info("Step 4: attempting cmbagent.one_shot(researcher) for archetypes")
    researcher_text = await _async_researcher(prompt)

    if researcher_text:
        arr = _extract_json_array(researcher_text)
        if arr and len(arr) >= 2:
            logger.info("Step 4: researcher returned valid JSON array (%d items)", len(arr))
            return [{"id": f"arch-{i}", **arch} for i, arch in enumerate(arr)]

        # Researcher returned text but not structured — feed to LLM for structuring
        logger.info("Step 4: researcher returned text (%d chars), structuring via LLM", len(researcher_text))
        structure_prompt = f"""Extract and organize the following research into the JSON array format below. Do NOT invent new information.

### Raw Research
{researcher_text[:15000]}

### Required format (return ONLY valid JSON array):
[{{"title":"...","summary":"...","coreApproach":"...","personas":["..."],"benefits":["..."],"technologyEnablers":["..."],"implementationComplexity":"...","references":["..."]}}]"""
        try:
            structured = await _async_llm_direct(structure_prompt, _SYSTEM_STRATEGIST, temperature=0.3)
            arr2 = _extract_json_array(structured)
            if arr2 and len(arr2) >= 2:
                return [{"id": f"arch-{i}", **arch} for i, arch in enumerate(arr2)]
        except Exception as e:
            logger.warning("Step 4: structuring researcher output failed: %s", e)

    # --- Fallback: direct LLM ---
    logger.info("Step 4: falling back to direct LLM for archetypes")
    content = await _async_llm_direct(prompt, "You are a senior product discovery strategist.")

    arr = _extract_json_array(content)
    if arr:
        return [{"id": f"arch-{i}", **arch} for i, arch in enumerate(arr)]

    return []


async def generate_features(
    selected_archetype: Dict[str, Any],
    opportunity: Dict[str, Any],
    intake_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Step 5: Generate feature set.
    Primary: cmbagent.one_shot(researcher) for research-backed features.
    Fallback: direct LLM for structured JSON generation.
    """
    process_info = (
        f"Existing Process - {intake_data.get('existingFunctionality', '')}"
        if intake_data.get('processType') == 'existing'
        else 'New Process'
    )

    prompt = f"""You are a senior Product Manager and Feature Architect at Domain Consulting Group. Generate a comprehensive, production-grade feature set for this solution.

CRITICAL: ALL success metrics, performance targets, and benchmark figures MUST be grounded in REAL industry standards and documented case studies. Use verifiable benchmarks from real implementations. Never fabricate performance numbers.Solution Archetype: {selected_archetype.get('title', '')}
{selected_archetype.get('summary', '')}
Core Approach: {selected_archetype.get('coreApproach', '')}

Opportunity Context: {opportunity.get('title', '')}
{opportunity.get('explanation', '')}

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {process_info}
- Problem Keywords: {intake_data.get('problemKeywords', '')}

### Requirements
- Consider the client's specific context, tech stack, organizational constraints, and strategic priorities.
- Features must span the full solution: Core Features, Analytics & Intelligence, Integration & Data, UX/UI, Admin & Governance, and Automation.
- Be SPECIFIC: reference real technologies, APIs, data sources, and methodologies where relevant.
- Think end-to-end: from data ingestion through processing, insight generation, user interaction, and feedback loops.
- Provide 10 to 15 features across multiple buckets. Ensure a good mix of Must/Should/Could priorities.

For each feature provide:
1. Feature name (clear and descriptive)
2. Description (3-5 sentences: what it does, how it works, what user need it satisfies, and what makes it valuable)
3. Strategic Goal (2-3 sentences: how this feature connects to the broader business objective and ROI)
4. User Stories (4-6 stories starting with "As a..." — cover different personas and scenarios)
5. Success Metrics (4-6 measurable criteria with specific targets — e.g., "Dashboard load time < 2 seconds for 95th percentile")
6. Acceptance Criteria (3-5 testable conditions — e.g., "System processes 10,000 records per minute without degradation")
7. Bucket/category (Core Features, Analytics, Integration, UX/UI, Admin, Automation)
8. Priority tag (Must, Should, or Could)
9. Effort estimate (Small/Medium/Large)

Format as JSON array:
[
  {{
    "name": "...",
    "description": "...",
    "strategicGoal": "...",
    "userStories": ["As a...", "As a...", "As a...", "As a..."],
    "successMetrics": ["...", "...", "...", "..."],
    "acceptanceCriteria": ["...", "...", "..."],
    "bucket": "...",
    "priority": "Must|Should|Could",
    "effort": "Small|Medium|Large"
  }}
]"""

    # --- Primary: try cmbagent researcher ---
    logger.info("Step 5: attempting cmbagent.one_shot(researcher) for features")
    researcher_text = await _async_researcher(prompt)

    if researcher_text:
        arr = _extract_json_array(researcher_text)
        if arr and len(arr) >= 3:
            logger.info("Step 5: researcher returned valid JSON array (%d items)", len(arr))
            return [
                {"id": f"feat-{i}", "selected": feat.get("priority") == "Must", **feat}
                for i, feat in enumerate(arr)
            ]

        # Researcher returned text but not structured — feed to LLM for structuring
        logger.info("Step 5: researcher returned text (%d chars), structuring via LLM", len(researcher_text))
        structure_prompt = f"""Extract and organize the following research into the JSON array format below. Do NOT invent new information.

### Raw Research
{researcher_text[:15000]}

### Required format (return ONLY valid JSON array):
[{{"name":"...","description":"...","strategicGoal":"...","userStories":["As a..."],"successMetrics":["..."],"acceptanceCriteria":["..."],"bucket":"...","priority":"Must|Should|Could","effort":"Small|Medium|Large"}}]"""
        try:
            structured = await _async_llm_direct(structure_prompt, _SYSTEM_STRATEGIST, temperature=0.3)
            arr2 = _extract_json_array(structured)
            if arr2 and len(arr2) >= 3:
                return [
                    {"id": f"feat-{i}", "selected": feat.get("priority") == "Must", **feat}
                    for i, feat in enumerate(arr2)
                ]
        except Exception as e:
            logger.warning("Step 5: structuring researcher output failed: %s", e)

    # --- Fallback: direct LLM ---
    logger.info("Step 5: falling back to direct LLM for features")
    content = await _async_llm_direct(prompt, "You are a product manager and feature architect.")

    arr = _extract_json_array(content)
    if arr:
        return [
            {"id": f"feat-{i}", "selected": feat.get("priority") == "Must", **feat}
            for i, feat in enumerate(arr)
        ]

    return []


async def generate_prompts(
    intake_data: Dict[str, Any],
    opportunity: Dict[str, Any],
    archetype: Dict[str, Any],
    selected_features: List[Dict[str, Any]],
) -> Dict[str, str]:
    """
    Step 6: Generate builder prompts.
    Uses direct LLM for structured generation.
    """
    feature_list = ", ".join(f.get("name", "") for f in selected_features)

    prompt = f"""You are an expert prompt engineer and product strategist at Domain Consulting Group. Generate three comprehensive, production-ready builder prompts for this solution.

CRITICAL: All data, statistics, metrics, and benchmarks embedded in the prompts MUST be REAL and VERIFIABLE. The generated applications should use and display factual information from real sources.

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {'Existing Process - ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}
- Problem Keywords: {intake_data.get('problemKeywords', '')}

Problem: {intake_data.get('problemKeywords', '')}
Opportunity: {opportunity.get('title', '')} - {opportunity.get('explanation', '')}
Solution: {archetype.get('title', '')} - {archetype.get('summary', '')}
Core Approach: {archetype.get('coreApproach', '')}
Features: {feature_list}

### Requirements
- Each prompt must be COMPREHENSIVE — at least 500 words — covering the full solution scope.
- Include problem context, opportunity rationale, solution archetype, ALL selected features with their descriptions, suggested screens & flows, data model considerations, integration points, and technical architecture guidance.
- Incorporate client-specific context, organizational considerations, and integration requirements throughout.
- Each prompt should be self-contained — a developer should be able to build the entire solution from the prompt alone.

Generate:
1. A Lovable app prompt (optimized for Lovable's AI app builder — focus on UI components, pages, user flows, styling, and real-time features)
2. A Google AI Studio prompt (optimized for Gemini — focus on AI/ML capabilities, data processing, and intelligent features)
3. A general LLM prompt (works with any LLM — comprehensive technical specification including architecture, APIs, database schema, and deployment)

Format as JSON:
{{
  "lovable": "Complete Lovable prompt (500+ words)...",
  "googleAI": "Complete Google AI Studio prompt (500+ words)...",
  "general": "Complete general LLM prompt (500+ words)..."
}}"""

    content = await _async_llm_direct(prompt, "You are an expert prompt engineer.")

    parsed = _extract_json_object(content)
    if parsed:
        def stringify(value):
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                return "\n\n".join(
                    f"{k}:\n{chr(10).join(v) if isinstance(v, list) else v}"
                    for k, v in value.items()
                )
            return str(value)

        return {
            "lovable": stringify(parsed.get("lovable", "")),
            "googleAI": stringify(parsed.get("googleAI", "")),
            "general": stringify(parsed.get("general", "")),
        }

    return {"lovable": content, "googleAI": content, "general": content}


async def generate_slide_content(
    intake_data: Dict[str, Any],
    research: str,
    problem: str,
    opportunity: Dict[str, Any],
    archetype: Dict[str, Any],
    features: List[Dict[str, Any]],
) -> str:
    """
    Step 7: Generate COMPREHENSIVE presentation slide content.
    Uses direct LLM for structured Markdown generation.
    Generates a very long, detailed report (30+ slides, 5000+ words).
    """
    feature_list = "\n".join(
        f"- **{f.get('name', '')}** ({f.get('priority', '')}): {f.get('description', '')}"
        for f in features if f.get("selected", False)
    )
    feature_stories = "\n".join(
        f"  - {f.get('name', '')}: {'; '.join(f.get('userStories', []))}"
        for f in features if f.get("selected", False)
    )
    feature_metrics = "\n".join(
        f"  - {f.get('name', '')}: {'; '.join(f.get('successMetrics', []))}"
        for f in features if f.get("selected", False)
    )

    prompt = f"""You are a senior presentation expert, management consultant, and product strategist at Domain Consulting Group. Generate an EXTREMELY COMPREHENSIVE, executive-ready presentation report for this product discovery engagement. This is the FINAL deliverable that goes to the C-suite — it must be thorough, data-rich, and professional.

CRITICAL REQUIREMENTS:
1. This report MUST be 5,000-8,000 words minimum. Do NOT be brief. Every section needs DEEP detail.
2. ALL statistics, market sizes, growth rates, ROI figures, improvement percentages, and benchmark data MUST be REAL and VERIFIABLE from actual industry sources (Gartner, McKinsey, Forrester, Statista, IDC, Deloitte, BCG, company earnings, SEC filings).
3. NEVER fabricate numbers. If you say "40% improvement" or "$4B market", it MUST be a real documented figure.
4. Include source citations in parentheses after data points, e.g., "(Source: Gartner 2024)" or "(McKinsey Global Survey, 2023)".
5. Each slide section should have 8-15 detailed bullet points with substantive content.
6. Include detailed speaker notes for EVERY slide marked with [SPEAKER NOTES: ...]

Client Information:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {'Existing Process - ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}
- Problem Keywords: {intake_data.get('problemKeywords', '')}

Research Context:
{research}

Problem:
{problem}

Opportunity: {opportunity.get('title', '')}
{opportunity.get('explanation', '')}
Value Category: {opportunity.get('valueCategory', '')}
KPIs: {', '.join(opportunity.get('kpis', []))}
Why Now: {opportunity.get('whyNow', '')}
Implementation Notes: {opportunity.get('implementationNotes', '')}

Solution: {archetype.get('title', '')}
{archetype.get('summary', '')}
Core Approach: {archetype.get('coreApproach', '')}
Technology Enablers: {', '.join(archetype.get('technologyEnablers', []))}
Implementation Complexity: {archetype.get('implementationComplexity', '')}

Features (with descriptions):
{feature_list}

Feature User Stories:
{feature_stories}

Feature Success Metrics:
{feature_metrics}

### REQUIRED SLIDE STRUCTURE — Generate ALL of these sections with MAXIMUM detail:

## Slide 1: Title Slide
- Engagement title, client name, date, DCG branding, engagement team

## Slide 2: Table of Contents
- Numbered list of all sections

## Slide 3: Executive Summary
- 8-10 bullets covering: the problem, market context, selected opportunity, proposed solution, expected impact, timeline, investment range, and strategic alignment
- [SPEAKER NOTES: 3-4 sentences framing the narrative]

## Slide 4: Engagement Overview & Methodology
- Discovery methodology used, stakeholders involved, research approach, data sources consulted
- 6-8 bullets detailing the rigorous approach

## Slide 5: Client Landscape & Current State
- Detailed analysis of the client's current position: market share, digital maturity, organizational structure, tech stack, recent initiatives
- 8-10 bullets with real data about the client

## Slide 6: Problem Statement Deep Dive
- The core problem with evidence and urgency
- Root cause analysis (3 levels deep)
- Impact quantification with real metrics
- 10-12 bullets with specific data

## Slide 7: Market Context & Industry Trends
- 8-12 key market trends with REAL data points and sources
- Market size, growth rates, adoption curves — all verifiable

## Slide 8: Competitive Landscape Analysis
- 8-10 real competitor moves with company names, dates, and specifics
- Market positioning map description
- Competitive threats and differentiation opportunities

## Slide 9: Industry Pain Points & Market Gaps
- 8-10 documented pain points with real impact data
- Gap analysis showing unmet needs
- Cross-reference with client-specific challenges

## Slide 10: Stakeholder Impact Analysis
- Personas affected with detailed pain descriptions
- Frequency and severity assessment
- Current workaround costs (quantified with real benchmarks)
- 8-10 persona-impact bullets

## Slide 11: Opportunity Analysis — Selected Opportunity
- Deep dive into the selected opportunity
- Value drivers and business case
- KPIs with current baselines and target improvements (real benchmarks)
- Why-now justification with market timing evidence
- 10-12 detailed bullets

## Slide 12: Alternative Opportunities Considered
- Brief overview of other opportunity areas evaluated
- Why the selected opportunity was chosen
- 6-8 bullets

## Slide 13: Solution Architecture Overview
- The selected solution archetype: what it is, how it works
- Core approach and differentiation
- Technology stack and integration points
- 10-12 bullets

## Slide 14: Solution — User Experience & Workflows
- Key user journeys and interaction patterns
- Screen/module descriptions
- Persona-specific workflows
- 8-10 bullets

## Slide 15: Solution — Technical Architecture
- System architecture components
- Data flow and integration patterns
- API strategy and third-party integrations
- Security and compliance considerations
- 8-10 bullets

## Slide 16: Feature Set — Must Have (Priority 1)
- All Must-priority features with full descriptions
- User stories and acceptance criteria for each
- Success metrics for each feature
- 8-12 bullets

## Slide 17: Feature Set — Should Have & Could Have
- Should/Could-priority features with descriptions
- Strategic value of each
- 6-10 bullets

## Slide 18: Feature Dependency & Integration Map
- How features relate to each other
- Integration points and data dependencies
- Build sequence rationale
- 6-8 bullets

## Slide 19: Value Drivers & ROI Analysis
- Detailed ROI calculation framework
- Expected business impact with REAL industry benchmarks
- Revenue impact, cost savings, efficiency gains — all with verifiable numbers
- Payback period estimates based on real case studies
- 10-12 bullets

## Slide 20: Success Metrics & KPI Dashboard
- Complete KPI framework with baselines and targets
- Measurement methodology
- Reporting cadence and governance
- 8-10 bullets

## Slide 21: User Personas & Journey Maps
- Detailed persona profiles (3-5 personas)
- Current vs. future state journey for each
- Pain points resolved and value delivered
- 10-12 bullets

## Slide 22: Data Strategy & Analytics
- Data sources required
- Analytics capabilities and insights
- ML/AI models and their business value
- Data governance considerations
- 8-10 bullets

## Slide 23: Implementation Roadmap — Phase 1: Quick Wins (0-3 months)
- Specific deliverables and milestones
- Team composition and effort estimates
- Expected outcomes with metrics
- 8-10 bullets

## Slide 24: Implementation Roadmap — Phase 2: Foundation (3-6 months)
- Core platform buildout details
- Integration milestones
- Training and change management
- 8-10 bullets

## Slide 25: Implementation Roadmap — Phase 3: Scale & Optimize (6-12 months)
- Advanced features and optimizations
- Scale-out plan
- Continuous improvement framework
- 8-10 bullets

## Slide 26: Resource Requirements & Team Structure
- Team composition (roles, FTE estimates)
- Skill requirements
- Training and onboarding plan
- 6-8 bullets

## Slide 27: Investment & Budget Guidance
- High-level cost ranges for each phase (use real industry benchmarks for similar implementations)
- Infrastructure costs, licensing, and operational expenses
- Total cost of ownership (TCO) framework
- 6-8 bullets

## Slide 28: Risk Assessment & Mitigation
- 8-10 identified risks with probability and impact
- Mitigation strategies for each
- Contingency plans

## Slide 29: Change Management & Adoption Strategy
- Stakeholder communication plan
- Training approach
- Adoption metrics and targets
- 6-8 bullets

## Slide 30: Prototype & POC Recommendations
- What to build first as proof of concept
- POC success criteria
- Timeline and resources needed
- How to use the generated builder prompts
- 6-8 bullets

## Slide 31: Next Steps & Call to Action
- 8-10 concrete next steps with owners, timelines, and dependencies
- Decision points and governance structure
- Immediate actions (next 2 weeks)

## Slide 32: Appendix A — Research References
- Complete list of ALL sources cited throughout the report
- Organized by category (market reports, case studies, analyst publications)

## Slide 33: Appendix B — Detailed Feature Specifications
- Full feature list with all user stories and success metrics

## Slide 34: Appendix C — Glossary & Definitions
- Key terms and definitions used in the report

Format as markdown with ## for slide titles, ### for sub-sections, and - for bullets.
REMINDER: 5,000-8,000 words minimum. Be EXHAUSTIVE. Include [SPEAKER NOTES: ...] for every content slide."""

    content = await _async_llm_direct(
        prompt,
        "You are a management consultant and presentation expert. "
        "You MUST use ONLY real, verifiable data and statistics from actual sources. "
        "This is a COMPREHENSIVE final report — be extremely thorough. "
        "Target 5,000-8,000 words minimum.",
        max_tokens=16000,
    )
    return content


# ---------------------------------------------------------------------------
# Deep Research mode using Planning & Control
# ---------------------------------------------------------------------------

async def deep_research(
    intake_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Optional: Use cmbagent's full Planning & Control pipeline for
    deep multi-step research. Returns plan, step results, and artifacts.
    
    This is for cases where the user wants a thorough, multi-agent
    research process rather than single-shot generation.
    """
    task = f"""Conduct comprehensive product discovery research:

Client: {intake_data.get('clientName', '')}
Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
Context: {intake_data.get('clientContext', '')}
Business Function: {intake_data.get('businessFunction', '')}
Problem/Keywords: {intake_data.get('problemKeywords', '')}

Your goal is to produce:
1. Market analysis and competitive landscape
2. Industry pain points and unmet needs
3. Opportunity areas with value assessment
4. Solution recommendations with feature sets
5. Implementation considerations

Save all findings as structured JSON files in the working directory."""

    results = await _async_planning_control(task)

    # Extract structured output from P&C results
    chat_history = results.get('chat_history', [])
    final_context = results.get('final_context', {})

    return {
        "run_id": results.get('run_id', ''),
        "chat_history_length": len(chat_history),
        "final_context": final_context,
        "phase_timings": results.get('phase_timings', {}),
    }
