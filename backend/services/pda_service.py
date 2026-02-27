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
    max_tokens: int = 4096,
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
    max_tokens: int = 4096,
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
    "opportunity spaces.  Always return ONLY valid JSON — no markdown, no prose."
)


async def get_client_details(client_name: str) -> Dict[str, Any]:
    """
    Step 0 helper: Auto-detect client industry/sub-industry/functions.
    Uses direct LLM via cmbagent provider.
    """
    prompt = f"""You are a business intelligence assistant. Based on the client/company name provided, identify their industry, sub-industry, and relevant business functions.

Client/Company Name: {client_name}

Provide accurate, research-backed information about this organization. If the company is well-known, use your knowledge. If uncertain, make reasonable inferences based on the company name.

Return ONLY valid JSON with no markdown formatting, using this exact structure:
{{
  "industry": "Primary industry (e.g., Retail, Healthcare, Financial Services, Technology, Manufacturing)",
  "subIndustry": "More specific sub-industry (e.g., Fashion Retail, Investment Banking, Cloud Services)",
  "businessFunctions": ["Function 1", "Function 2", "Function 3"]
}}

Business functions should be selected from: Store Ops, Supply Chain, Merchandising, E-commerce, HR, Finance, Manufacturing, Marketing. Include 2-4 most relevant functions for this client."""

    content = await _async_llm_direct(prompt, "You are a business intelligence assistant specializing in company analysis.")

    parsed = _extract_json_object(content)
    if parsed:
        return {
            "industry": parsed.get("industry", ""),
            "subIndustry": parsed.get("subIndustry", ""),
            "businessFunctions": parsed.get("businessFunctions", []),
        }

    return {"industry": "", "subIndustry": "", "businessFunctions": []}


async def generate_research_summary(intake_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step 1: Generate research summary.

    Primary path: cmbagent.one_shot(agent='researcher') for web-search-augmented research.
    Fallback: direct LLM via create_openai_client() if the researcher fails.
    """
    research_prompt = _build_research_prompt(intake_data)

    # --- Primary: use cmbagent researcher agent ---
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
{researcher_text[:6000]}

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
3. Level of Detail: Clear, non-fluffy, consulting-style language. Each item should be 1-2 sentences, specific and actionable.
4. Total 3 to 6 points per section.

### Output Format (JSON only)
Return ONLY valid JSON, no markdown, no explanations:
{{
  "marketTrends": ["Each item: a concrete trend related to the Problem/Keywords. 3-6 items."],
  "competitorMoves": ["Each item: a specific competitor move relevant to the Problem/Keywords. 3-6 items."],
  "industryPainPoints": ["Each item: a concrete pain point tied to the Problem/Keywords. 3-6 items."],
  "workshopAngles": ["Each item: a sharp angle for a product discovery workshop. 3-6 items."],
  "references": ["Each item: a specific, authoritative reference. 3-6 items."]
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

    prompt = f"""Based on the following research and inputs, generate a crisp problem definition:

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

Consider the client's specific context, organizational maturity, and strategic priorities when framing the problem.

Return ONLY valid JSON, no prefix or suffix text:
{{
  "problemStatement": "A crisp 1-2 line problem statement",
  "supportingPoints": ["point 1", "point 2", "point 3"],
  "personasAffected": ["persona 1", "persona 2", "persona 3"],
  "kpisImpacted": ["kpi 1", "kpi 2", "kpi 3"],
  "rootCause": "Root cause explanation (2-3 paragraphs)",
  "reframingExamples": ["example 1", "example 2"],
  "references": ["source 1", "source 2"]
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
            "references": parsed.get("references", []),
        }

    return {
        "problemStatement": content if content else "Unable to generate problem definition. Please retry.",
        "supportingPoints": [],
        "personasAffected": [],
        "kpisImpacted": [],
        "rootCause": "",
        "reframingExamples": [],
        "references": [],
    }


async def generate_opportunities(
    intake_data: Dict[str, Any],
    problem_definition: str,
) -> List[Dict[str, Any]]:
    """
    Step 3: Generate opportunity areas.
    Uses direct LLM for structured JSON generation.
    """
    prompt = f"""Based on the problem definition below, generate 3-5 specific opportunity areas:

{problem_definition}

Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {'Existing Process - Current functionality: ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}

Tailor opportunities to the client's specific context, organizational capabilities, and strategic priorities.

For each opportunity, provide:
1. Title (concise and compelling)
2. Short explanation
3. Value category (Revenue, Efficiency, Experience, or Risk)
4. KPIs influenced (2-4 specific metrics)
5. "Why now" justification

Format as JSON array with this structure, no prefix or suffix text:
[
  {{
    "title": "...",
    "explanation": "...",
    "valueCategory": "Revenue|Efficiency|Experience|Risk",
    "kpis": ["...", "..."],
    "whyNow": "...",
    "references": ["..."]
  }}
]"""

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
    Uses direct LLM for structured JSON generation.
    """
    prompt = f"""Based on this opportunity, generate 2-3 solution archetypes:

Opportunity: {selected_opportunity.get('title', '')}
{selected_opportunity.get('explanation', '')}
Value Category: {selected_opportunity.get('valueCategory', '')}

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Process Type: {'Existing Process - ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}

Tailor solution archetypes to the client's digital maturity, organizational capabilities, and strategic priorities.

Suggest solution archetypes such as: AI-powered assistant, Predictive engine, Automation co-pilot, Command center, Insights engine.

For each archetype, provide:
1. Title
2. Summary (2-3 sentences)
3. Personas who will use it (2-3)
4. Expected benefits (3-5 bullets)
5. References

Format as JSON array:
[
  {{
    "title": "...",
    "summary": "...",
    "personas": ["...", "..."],
    "benefits": ["...", "..."],
    "references": ["..."]
  }}
]"""

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
    Uses direct LLM for structured JSON generation.
    """
    prompt = f"""Generate a comprehensive feature set for this solution:

Solution: {selected_archetype.get('title', '')}
{selected_archetype.get('summary', '')}

Opportunity Context: {opportunity.get('title', '')}

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {'Existing Process - ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}

Consider the client's specific context, tech stack, organizational constraints, and strategic priorities.

Provide features organized by buckets (Core Features, Analytics, Integration, UX/UI, etc.)

For each feature provide:
1. Feature name
2. Description (2-3 sentences)
3. Strategic Goal (1-2 sentences)
4. User Stories (3-5 starting with "As a...")
5. Success Metrics (3-4 measurable criteria)
6. Bucket/category
7. Priority tag (Must, Should, or Could)

Format as JSON array:
[
  {{
    "name": "...",
    "description": "...",
    "strategicGoal": "...",
    "userStories": ["As a...", "As a...", "As a..."],
    "successMetrics": ["...", "...", "..."],
    "bucket": "...",
    "priority": "Must|Should|Could"
  }}
]"""

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

    prompt = f"""Generate three different prompts for building this solution:

Client Context:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {'Existing Process - ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}

Problem: {intake_data.get('problemKeywords', '')}
Opportunity: {opportunity.get('title', '')} - {opportunity.get('explanation', '')}
Solution: {archetype.get('title', '')} - {archetype.get('summary', '')}
Features: {feature_list}

Include client context, organizational considerations, and integration requirements.

Generate:
1. A Lovable app prompt (optimized for Lovable's AI app builder)
2. A Google AI Studio prompt (optimized for Gemini)
3. A general LLM prompt (works with any LLM)

Each prompt should include problem context, opportunity rationale, solution archetype, selected features, suggested screens & flows, technical considerations.

Format as JSON:
{{
  "lovable": "...",
  "googleAI": "...",
  "general": "..."
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
    Step 7: Generate presentation slide content.
    Uses direct LLM for structured Markdown generation.
    """
    feature_list = "\n".join(
        f"- {f.get('name', '')} ({f.get('priority', '')})"
        for f in features if f.get("selected", False)
    )

    prompt = f"""Generate presentation-ready slide content for this product discovery:

Client Information:
- Client: {intake_data.get('clientName', '')}
- Industry: {intake_data.get('industry', '')} - {intake_data.get('subIndustry', '')}
- Client Context: {intake_data.get('clientContext', '')}
- Business Function: {intake_data.get('businessFunction', '')}
- Process Type: {'Existing Process - ' + intake_data.get('existingFunctionality', '') if intake_data.get('processType') == 'existing' else 'New Process'}

Research Context:
{research}

Problem:
{problem}

Opportunity: {opportunity.get('title', '')}
{opportunity.get('explanation', '')}

Solution: {archetype.get('title', '')}
{archetype.get('summary', '')}

Features:
{feature_list}

Incorporate client-specific context throughout. Tailor recommendations based on organizational maturity.

Generate slide-ready bullet points for:
1. Problem Statement slide
2. Research Insights slide (3-5 key insights)
3. Opportunities slide
4. Solution Overview slide
5. Features & Capabilities slide
6. Value Drivers slide
7. Architecture Snapshot slide (high-level components)
8. Prototype Prompt slide (how to build it)
9. Next Steps slide

Format as markdown with clear slide titles (use ## for slides) and concise bullets.
Include references where applicable."""

    content = await _async_llm_direct(prompt, "You are a presentation expert and product strategist.")
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
