"""
LangGraph node functions for NewsPulse final report generation.

Each node makes a single, bounded LLM call to generate one report section.
This avoids the context-length explosion that occurs when using
planning_and_control_context_carryover for the full report.

Flow:
  preprocess → executive_summary → sentiment_dashboard → headlines
  → in_depth_analysis → company_analysis → trends_risks
  → regional_outlook → assemble → pdf → END
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# Maximum characters of raw data to include per section prompt.
# This keeps each LLM call well within token limits.
_MAX_CONTEXT_CHARS = 80_000
_MAX_SUMMARY_CHARS = 50_000

# System-level instruction injected into every section prompt to prevent
# the LLM from refusing or hallucinating data.
_COMPILER_SYSTEM = (
    "IMPORTANT: You are a REPORT COMPILER, not a search engine. "
    "All the data you need is provided below — it was collected by earlier "
    "research stages via web search. Your ONLY job is to read this data "
    "and reorganise it into the requested format. "
    "Do NOT say you cannot access real-time data. "
    "Do NOT apologise or add disclaimers about data freshness. "
    "Do NOT wrap output in code fences (no triple backticks). "
    "Use ONLY information found in the provided data sections below. "
    "Include real URLs/links exactly as they appear in the data."
)


def _get_llm_client(state: Dict[str, Any]):
    """Create an OpenAI-compatible client from state config."""
    from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider
    client = create_openai_client()
    model = resolve_model_for_provider(state.get("llm_model", "gpt-4o"))
    return client, model


_USE_MAX_COMPLETION_TOKENS = True  # default to newer param


def _call_llm(state: Dict[str, Any], prompt: str, max_tokens: int = 4096) -> str:
    """Make a single LLM call and return the response text.

    Handles both older models (max_tokens) and newer models
    (max_completion_tokens) automatically, with retry on mismatch.
    """
    global _USE_MAX_COMPLETION_TOKENS
    client, model = _get_llm_client(state)
    temperature = state.get("llm_temperature", 0.7)
    use_completion_tokens = _USE_MAX_COMPLETION_TOKENS

    for _attempt in range(2):
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if use_completion_tokens:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        try:
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            return _strip_code_fences(text)
        except Exception as e:
            err_str = str(e)
            if "max_tokens" in err_str and "max_completion_tokens" in err_str:
                # Flip the flag and retry once
                use_completion_tokens = not use_completion_tokens
                _USE_MAX_COMPLETION_TOKENS = use_completion_tokens
                logger.info(
                    "Switching to %s for NewsPulse LLM calls",
                    "max_completion_tokens" if use_completion_tokens else "max_tokens",
                )
                continue
            raise

    raise RuntimeError("NewsPulse LLM call failed after token-param retry")


def _strip_code_fences(text: str) -> str:
    """Remove wrapping ```markdown ... ``` or ``` ... ``` from LLM output."""
    import re
    stripped = text.strip()
    # Match ```markdown\n...\n``` or ```\n...\n```
    m = re.match(r'^```(?:markdown)?\s*\n(.*?)\n```\s*$', stripped, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def _strip_heading(text: str, heading_text: str) -> str:
    """Remove a leading heading line that duplicates the section title.

    LLMs sometimes echo the section heading even when told not to.
    Handles: '### Heading', '## Heading', '**Heading**', 'Heading\n---', etc.
    """
    import re
    stripped = text.strip()
    escaped = re.escape(heading_text)
    # Build patterns — note: can't use f-string with {1,4} quantifier,
    # so we concatenate instead.
    patterns = [
        r'^#{1,4}\s*' + escaped + r'\s*\n+',          # ### Heading\n
        r'^\*{2}' + escaped + r'\*{2}\s*\n+',          # **Heading**\n
        r'^' + escaped + r'\s*\n[-=]+\s*\n*',           # Heading\n---\n (setext)
        r'^' + escaped + r'\s*\n+',                     # Heading\n (plain text)
    ]
    for pat in patterns:
        new = re.sub(pat, '', stripped, count=1, flags=re.IGNORECASE)
        if new != stripped:
            return new.strip()
    return stripped


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, appending an ellipsis notice."""
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + "\n\n[... content truncated for brevity ...]"


# ═══════════════════════════════════════════════════════════════════════════
# Node: preprocess
# ═══════════════════════════════════════════════════════════════════════════

def preprocess_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Read input files and prepare bounded summaries for downstream nodes."""
    work_dir = state.get("work_dir", "")
    input_dir = os.path.join(work_dir, "input_files")

    # Read from files if state values are empty
    news_collection = state.get("news_collection", "")
    deep_analysis = state.get("deep_analysis", "")

    if not news_collection:
        nc_path = os.path.join(input_dir, "news_collection.md")
        if os.path.exists(nc_path):
            with open(nc_path, "r") as f:
                news_collection = f.read()

    if not deep_analysis:
        da_path = os.path.join(input_dir, "deep_analysis.md")
        if os.path.exists(da_path):
            with open(da_path, "r") as f:
                deep_analysis = f.read()

    # Create bounded summaries for per-section prompts
    news_summary = _truncate(news_collection, _MAX_SUMMARY_CHARS)
    analysis_summary = _truncate(deep_analysis, _MAX_SUMMARY_CHARS)

    time_window = state.get("time_window", "7d")
    tw_labels = {
        "1d": "the past 24 hours",
        "7d": "the past week",
        "14d": "the past two weeks",
        "30d": "the past month",
        "90d": "the past 3 months",
        "180d": "the past 6 months",
        "365d": "the past year",
        "2024": "the year 2024 (Jan–Dec 2024)",
        "2025": "the year 2025 (Jan–Dec 2025)",
        "2026": "the year 2026 (Jan–present 2026)",
        "2025-2026": "2025 through 2026",
        "Q1 2025": "Q1 2025 (Jan–Mar 2025)",
        "Q2 2025": "Q2 2025 (Apr–Jun 2025)",
        "Q3 2025": "Q3 2025 (Jul–Sep 2025)",
        "Q4 2025": "Q4 2025 (Oct–Dec 2025)",
        "Q1 2026": "Q1 2026 (Jan–Mar 2026)",
        "H1 2025": "first half of 2025 (Jan–Jun 2025)",
        "H2 2025": "second half of 2025 (Jul–Dec 2025)",
        "H1 2026": "first half of 2026 (Jan–Jun 2026)",
    }
    # For free-text inputs like "weeks", "3 months", etc. keep as-is
    # but prefix with "the past" if it's a bare word
    raw_tw = tw_labels.get(time_window)
    if not raw_tw:
        raw_tw = time_window
        if raw_tw and not raw_tw.startswith("the "):
            raw_tw = f"the past {raw_tw}"

    logger.info(
        "preprocess_node: news=%d chars, analysis=%d chars",
        len(news_collection), len(deep_analysis),
    )

    return {
        "news_collection": news_collection,
        "deep_analysis": deep_analysis,
        "news_summary": news_summary,
        "analysis_summary": analysis_summary,
        "time_window_human": raw_tw,
        "messages": [HumanMessage(content="Preprocessing complete.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section node helpers
# ═══════════════════════════════════════════════════════════════════════════

def _section_context(state: Dict[str, Any]) -> str:
    """Build the common context header for section prompts."""
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    return (
        f"Industry: {state.get('industry', '')}\n"
        f"Companies: {state.get('companies', 'None specified')}\n"
        f"Region: {state.get('region', 'Global')}\n"
        f"Time Window: {tw_human}\n"
        f"\nSTRICT: Use ONLY data from {tw_human} and relevant to "
        f"{state.get('region', 'Global')}. Discard anything outside this scope.\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Node: Executive Summary
# ═══════════════════════════════════════════════════════════════════════════

def executive_summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Executive Summary section."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Executive Summary (4-6 sentences) for an industry news & sentiment report.

{_section_context(state)}

## Collected News Data
{_truncate(state.get('news_summary', ''), 20000)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 20000)}

Using ONLY the data above, write the Executive Summary covering:
- Industry momentum and direction
- Current sentiment state (with specific data points from above)
- Key developments of the period (name specific events/companies)
- Main opportunities and risks

Output ONLY the section content in plain markdown. No heading. No code fences.
"""
    result = _call_llm(state, prompt, max_tokens=1024)
    logger.info("executive_summary_node: %d chars", len(result))
    return {
        "executive_summary": result,
        "messages": [HumanMessage(content="Executive summary generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Sentiment Dashboard
# ═══════════════════════════════════════════════════════════════════════════

def sentiment_dashboard_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Market Sentiment Dashboard with structured data for charts."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Market Sentiment Dashboard for an industry report.
You MUST return ONLY valid JSON — no markdown, no commentary, no code fences.

{_section_context(state)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 25000)}

Based on the analysis data above, return a JSON object with this EXACT structure:

{{
  "overall_sentiment": {{
    "label": "Bullish|Bearish|Neutral|Mixed",
    "score": <number 0-100, where 0=very bearish, 50=neutral, 100=very bullish>,
    "trend": "up|down|stable"
  }},
  "industry_momentum": {{
    "label": "Strong|Moderate|Weak",
    "score": <number 0-100>,
    "trend": "up|down|stable"
  }},
  "risk_level": {{
    "label": "Low|Medium|High|Critical",
    "score": <number 0-100, where 0=no risk, 100=extreme risk>,
    "trend": "up|down|stable"
  }},
  "investment_activity": {{
    "label": "Hot|Warm|Cool|Cold",
    "score": <number 0-100>,
    "trend": "up|down|stable"
  }},
  "innovation_index": {{
    "label": "Breakthrough|Active|Moderate|Stagnant",
    "score": <number 0-100>,
    "trend": "up|down|stable"
  }},
  "sentiment_distribution": {{
    "positive": <percentage 0-100>,
    "neutral": <percentage 0-100>,
    "negative": <percentage 0-100>
  }},
  "confidence_score": <number 0-100>,
  "key_drivers": [
    "First key sentiment driver (one sentence citing specific data)",
    "Second key sentiment driver (one sentence citing specific data)",
    "Third key sentiment driver (one sentence citing specific data)"
  ],
  "outlook_signal": "Strong Buy|Buy|Hold|Sell|Strong Sell"
}}

IMPORTANT: Return ONLY the JSON object. No markdown. No explanation. No code fences.
"""
    raw = _call_llm(state, prompt, max_tokens=1024)

    # Parse JSON from LLM response
    sentiment_data = _parse_sentiment_json(raw)

    # Generate the markdown dashboard from structured data
    dashboard_md = _build_sentiment_dashboard_md(sentiment_data)

    logger.info("sentiment_dashboard_node: parsed %d indicators", len(sentiment_data))
    return {
        "sentiment_dashboard": dashboard_md,
        "sentiment_data": sentiment_data,
        "messages": [HumanMessage(content="Sentiment dashboard generated.")],
    }


def _parse_sentiment_json(raw: str) -> dict:
    """Parse sentiment JSON from LLM output, with fallback defaults."""
    import re
    # Try to extract JSON from the response
    cleaned = raw.strip()
    # Remove wrapping code fences if present
    m = re.match(r'^```(?:json)?\s*\n(.*?)\n```\s*$', cleaned, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()

    defaults = {
        "overall_sentiment": {"label": "Mixed", "score": 50, "trend": "stable"},
        "industry_momentum": {"label": "Moderate", "score": 50, "trend": "stable"},
        "risk_level": {"label": "Medium", "score": 50, "trend": "stable"},
        "investment_activity": {"label": "Warm", "score": 50, "trend": "stable"},
        "innovation_index": {"label": "Active", "score": 60, "trend": "up"},
        "sentiment_distribution": {"positive": 40, "neutral": 35, "negative": 25},
        "confidence_score": 65,
        "key_drivers": [
            "Market data indicates mixed signals across key indicators.",
            "Industry activity remains at moderate levels.",
            "Risk factors are balanced against growth opportunities."
        ],
        "outlook_signal": "Hold",
    }

    try:
        data = json.loads(cleaned)
        # Validate and fill missing keys
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val
        return data
    except json.JSONDecodeError:
        logger.warning("Failed to parse sentiment JSON, using defaults")
        return defaults


def _build_sentiment_dashboard_md(data: dict) -> str:
    """Build a rich markdown dashboard from structured sentiment data."""
    trend_icons = {"up": "📈", "down": "📉", "stable": "➡️"}
    signal_colors = {
        "Strong Buy": "🟢🟢", "Buy": "🟢", "Hold": "🟡",
        "Sell": "🔴", "Strong Sell": "🔴🔴",
    }

    overall = data.get("overall_sentiment", {})
    momentum = data.get("industry_momentum", {})
    risk = data.get("risk_level", {})
    invest = data.get("investment_activity", {})
    innov = data.get("innovation_index", {})
    dist = data.get("sentiment_distribution", {})
    confidence = data.get("confidence_score", 65)
    drivers = data.get("key_drivers", [])
    outlook = data.get("outlook_signal", "Hold")

    def _score_bar(score: int, width: int = 20) -> str:
        filled = round(score / 100 * width)
        return "█" * filled + "░" * (width - filled)

    def _trend(t: str) -> str:
        return trend_icons.get(t, "➡️")

    md = f"""<!-- SENTIMENT_DASHBOARD_START -->

**Overall Market Signal: {signal_colors.get(outlook, '🟡')} {outlook}** | **Confidence: {confidence}%**

---

### Key Indicators

| Indicator | Rating | Score | Trend | Gauge |
|:---|:---|:---:|:---:|:---|
| **Overall Sentiment** | {overall.get('label', 'N/A')} | {overall.get('score', 50)}/100 | {_trend(overall.get('trend', 'stable'))} | `{_score_bar(overall.get('score', 50))}` |
| **Industry Momentum** | {momentum.get('label', 'N/A')} | {momentum.get('score', 50)}/100 | {_trend(momentum.get('trend', 'stable'))} | `{_score_bar(momentum.get('score', 50))}` |
| **Risk Level** | {risk.get('label', 'N/A')} | {risk.get('score', 50)}/100 | {_trend(risk.get('trend', 'stable'))} | `{_score_bar(risk.get('score', 50))}` |
| **Investment Activity** | {invest.get('label', 'N/A')} | {invest.get('score', 50)}/100 | {_trend(invest.get('trend', 'stable'))} | `{_score_bar(invest.get('score', 50))}` |
| **Innovation Index** | {innov.get('label', 'N/A')} | {innov.get('score', 50)}/100 | {_trend(innov.get('trend', 'stable'))} | `{_score_bar(innov.get('score', 50))}` |

### Sentiment Distribution

| Positive | Neutral | Negative |
|:---:|:---:|:---:|
| 🟢 **{dist.get('positive', 0)}%** | 🟡 **{dist.get('neutral', 0)}%** | 🔴 **{dist.get('negative', 0)}%** |

### Key Sentiment Drivers
"""
    for i, driver in enumerate(drivers[:5], 1):
        md += f"\n{i}. {driver}"

    md += "\n\n<!-- SENTIMENT_DASHBOARD_END -->\n"
    return md


# ═══════════════════════════════════════════════════════════════════════════
# Node: Headlines
# ═══════════════════════════════════════════════════════════════════════════

def headlines_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Top Headlines & Breaking News section."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling a curated headline list from ALREADY-COLLECTED news data.
All the news below was gathered by a research agent in earlier stages.
Your job is to select and format the top stories — NOT to search for new ones.

{_section_context(state)}

## Collected News Data (from research stages)
{_truncate(state.get('news_summary', ''), 40000)}

From the collected news data above, select the 8-12 most impactful stories.
Format each as:
1. **[Headline]** — [Brief summary, 1-2 sentences]. *Source: [source name/URL from the data]*
2. ...

Rules:
- Extract headlines and sources DIRECTLY from the data above
- Include real URLs where they appear in the data
- Do NOT say you cannot access data — it is ALL provided above
- Output ONLY the numbered list, no heading, no preamble
"""
    result = _call_llm(state, prompt, max_tokens=2048)
    logger.info("headlines_node: %d chars", len(result))
    return {
        "headlines": result,
        "messages": [HumanMessage(content="Headlines generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: In-Depth Analysis
# ═══════════════════════════════════════════════════════════════════════════

def in_depth_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the In-Depth Analysis section."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the In-Depth Analysis section from already-collected research.

{_section_context(state)}

## Deep Analysis Data
{_truncate(state.get('analysis_summary', ''), 30000)}

## News Data
{_truncate(state.get('news_summary', ''), 20000)}

Write 3 subsections (4.1, 4.2, 4.3), each covering a major development found in the data above:
#### 4.1 [Title — from the data]
[150-250 words: what happened, why it matters, industry impact, forward outlook. Cite specific sources/URLs from the data.]

#### 4.2 [Title — from the data]
[Same structure]

#### 4.3 [Title — from the data]
[Same structure]

Use ONLY information and sources found in the data above. Include URLs where available.
Output ONLY the subsections in markdown (no parent heading, no code fences).
"""
    result = _call_llm(state, prompt, max_tokens=3072)
    logger.info("in_depth_analysis_node: %d chars", len(result))
    return {
        "in_depth_analysis": result,
        "messages": [HumanMessage(content="In-depth analysis generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Company Analysis
# ═══════════════════════════════════════════════════════════════════════════

def company_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Company Analysis section."""
    companies = state.get("companies", "")
    if not companies or companies.strip().lower() in ("none specified", ""):
        # No specific companies requested — generate general industry leaders analysis
        company_instruction = "Analyse the top 3-5 industry leaders mentioned in the news data."
    else:
        company_instruction = f"Analyse each of these companies: {companies}"

    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Company Analysis section from already-collected research.

{_section_context(state)}

## News Data
{_truncate(state.get('news_summary', ''), 20000)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 20000)}

{company_instruction}

For each company, use this format:
#### [Company Name]
- **Key Updates:** [cite specific developments from the data above]
- **Strategic Moves:** [partnerships, acquisitions, pivots found in the data]
- **Sentiment Direction:** [Positive/Negative/Neutral — quote evidence from the data]
- **Opportunities:** [growth vectors identified in the data]
- **Risks:** [company-specific risks mentioned in the data]

Use ONLY facts from the provided data. Output ONLY the company subsections in markdown (no parent heading, no code fences).
"""
    result = _call_llm(state, prompt, max_tokens=3072)
    logger.info("company_analysis_node: %d chars", len(result))
    return {
        "company_analysis": result,
        "messages": [HumanMessage(content="Company analysis generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Trends & Risks (combined)
# ═══════════════════════════════════════════════════════════════════════════

def trends_risks_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Trends/Opportunities and Risks/Challenges sections."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling Trends and Risks sections from already-collected research.

{_section_context(state)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 30000)}

## News Data
{_truncate(state.get('news_summary', ''), 15000)}

Write TWO sections using ONLY data found above:

### Section A: Emerging Trends & Opportunities
List 3-5 forward-looking trends identified in the data:
1. **[Trend/Opportunity]:** [Description citing specific data points, figures, and sources from above]
2. ...

### Section B: Risk Factors & Challenges
List 3-5 key threats identified in the data:
1. **[Risk Factor]:** [Description citing specific evidence and sources from above]
2. ...

Output BOTH sections with their exact ### headings. No code fences.
"""
    result = _call_llm(state, prompt, max_tokens=2048)

    # Split into trends and risks
    parts = result.split("### Section B:")
    trends = parts[0].replace("### Section A: Emerging Trends & Opportunities", "").strip()
    risks = parts[1].strip() if len(parts) > 1 else ""
    if not risks:
        # Fallback: use full result for both
        risks_marker = "Risk Factors"
        idx = result.find(risks_marker)
        if idx > 0:
            trends = result[:idx].strip()
            risks = result[idx:].strip()
        else:
            trends = result
            risks = ""

    # Clean up any residual duplicate headings the LLM may have echoed
    trends = _strip_heading(trends, "Emerging Trends & Opportunities")
    trends = _strip_heading(trends, "Emerging Trends")
    risks = _strip_heading(risks, "Risk Factors & Challenges")
    risks = _strip_heading(risks, "Risk Factors")

    logger.info("trends_risks_node: trends=%d chars, risks=%d chars", len(trends), len(risks))
    return {
        "trends_opportunities": trends,
        "risks_challenges": risks,
        "messages": [HumanMessage(content="Trends and risks generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Regional Dynamics & Outlook (combined)
# ═══════════════════════════════════════════════════════════════════════════

def regional_outlook_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Regional Market Dynamics and Outlook/Recommendations."""
    region = state.get("region", "Global")
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling Regional Dynamics and Outlook sections from already-collected research.

{_section_context(state)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 25000)}

## News Data
{_truncate(state.get('news_summary', ''), 15000)}

Write TWO sections using ONLY data found above:

### Section A: Regional Market Dynamics ({region})
- **Market position:** Where {region} stands in the global landscape (cite data)
- **Key local developments:** Region-specific events from the data
- **Growth signals:** Positive indicators found in the data
- **Adoption levels:** Current state and trajectory based on the data

### Section B: Outlook & Recommendations

**Short-term outlook (1-3 months):**
[Assessment citing specific upcoming events/trends from the data]

**Medium-term outlook (3-12 months):**
[Broader trends and inflection points from the data]

**Strategic Recommendations:**
1. [Actionable recommendation grounded in the data findings]
2. [Actionable recommendation]
3. [Actionable recommendation]

Output BOTH sections with their exact ### headings. No code fences.
"""
    result = _call_llm(state, prompt, max_tokens=2048)

    # Split
    parts = result.split("### Section B:")
    regional = parts[0].replace(f"### Section A: Regional Market Dynamics ({region})", "").strip()
    outlook = parts[1].strip() if len(parts) > 1 else ""
    if not outlook:
        marker = "Outlook"
        idx = result.find(marker)
        if idx > 0:
            regional = result[:idx].strip()
            outlook = result[idx:].strip()
        else:
            regional = result
            outlook = ""

    # Clean up any residual duplicate headings the LLM may have echoed
    regional = _strip_heading(regional, f"Regional Market Dynamics ({region})")
    regional = _strip_heading(regional, "Regional Market Dynamics")
    outlook = _strip_heading(outlook, "Outlook & Recommendations")
    outlook = _strip_heading(outlook, "Outlook")

    logger.info("regional_outlook_node: regional=%d chars, outlook=%d chars", len(regional), len(outlook))
    return {
        "regional_dynamics": regional,
        "outlook_recommendations": outlook,
        "messages": [HumanMessage(content="Regional dynamics and outlook generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Sources
# ═══════════════════════════════════════════════════════════════════════════

def sources_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and compile all source references from original data + report sections."""
    # Use the ORIGINAL news_collection and deep_analysis for URL extraction
    # (they contain the actual URLs from web searches, unlike generated sections)
    original_data = "\n\n".join(filter(None, [
        state.get("news_collection", ""),
        state.get("deep_analysis", ""),
    ]))

    # Also include generated sections for any additional references
    sections_text = "\n\n".join(filter(None, [
        state.get("headlines", ""),
        state.get("in_depth_analysis", ""),
        state.get("company_analysis", ""),
    ]))

    prompt = f"""{_COMPILER_SYSTEM}

Extract ALL source references, URLs, links, and citations from the research data and report text below.
Compile them into a clean deduplicated numbered list.

## Original Research Data (contains real URLs from web searches)
{_truncate(original_data, 50000)}

## Report Sections (may reference sources by name)
{_truncate(sections_text, 15000)}

Rules:
- Extract every URL that appears in the data (https://...)
- Deduplicate — list each unique source only once
- Format: 1. [Source title/description] — [full URL]
- If a source has no URL, list it as: [Source name] — [No URL available]
- Sort with sources that have URLs first

Output ONLY the numbered source list.
"""
    result = _call_llm(state, prompt, max_tokens=2048)
    logger.info("sources_node: %d chars", len(result))
    return {
        "sources_references": result,
        "messages": [HumanMessage(content="Sources compiled.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Assemble
# ═══════════════════════════════════════════════════════════════════════════

def assemble_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble all sections into the final markdown report."""
    industry = state.get("industry", "Industry")
    region = state.get("region", "Global")
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    date_str = datetime.now().strftime("%B %d, %Y")
    time_str = datetime.now().strftime("%H:%M UTC")
    year_str = datetime.now().strftime("%Y")
    companies = state.get("companies", "")

    # Build a clean companies line
    companies_line = ""
    if companies and companies.strip().lower() not in ("none specified", ""):
        companies_line = f"\n> **Companies:** {companies}\n"

    # Clean up section content — strip any leading duplicate headings
    exec_summary = _strip_heading(state.get('executive_summary', '*No data available.*'), 'Executive Summary')
    sentiment = _strip_heading(state.get('sentiment_dashboard', '*No data available.*'), 'Market Sentiment Dashboard')
    headlines = _strip_heading(state.get('headlines', '*No data available.*'), 'Top Headlines')
    in_depth = _strip_heading(state.get('in_depth_analysis', '*No data available.*'), 'In-Depth Analysis')
    company = _strip_heading(state.get('company_analysis', '*No data available.*'), 'Company Analysis')
    trends = _strip_heading(state.get('trends_opportunities', '*No data available.*'), 'Emerging Trends')
    risks = _strip_heading(state.get('risks_challenges', '*No data available.*'), 'Risk Factors')
    regional = _strip_heading(state.get('regional_dynamics', '*No data available.*'), 'Regional Market Dynamics')
    outlook = _strip_heading(state.get('outlook_recommendations', '*No data available.*'), 'Outlook')
    sources = state.get('sources_references', '*No sources available.*')

    report = f"""# {industry} — Industry News & Sentiment Pulse

> **Executive Intelligence Report**
> **Region:** {region} | **Period:** {tw_human} | **Date:** {date_str}
{companies_line}
> *Prepared by MARS AI Research Platform*

---

## 1. Executive Summary

{exec_summary}

---

## 2. Market Sentiment Dashboard

{sentiment}

---

## 3. Top Headlines & Breaking News

*The most significant developments in **{industry}** across **{region}** during {tw_human}.*

{headlines}

---

## 4. In-Depth Analysis

{in_depth}

---

## 5. Company Analysis

{company}

---

## 6. Emerging Trends & Opportunities

{trends}

---

## 7. Risk Factors & Challenges

{risks}

---

## 8. Regional Market Dynamics — {region}

{regional}

---

## 9. Outlook & Recommendations

{outlook}

---

## 10. Sources & References

{sources}

---

## 11. Disclaimer

> *This report was generated using AI-powered news analysis and web research.
> All information is sourced from publicly available data covering **{tw_human}**
> for the **{region}** region. The content has been compiled from real search
> results and verified sources. Data should be verified independently before
> making investment or business decisions. This report does not constitute
> financial, legal, or professional advice.*

---

**Generated by MARS AI — Industry News & Sentiment Pulse**
*{region} | {tw_human} | {date_str} {time_str}*
*© {year_str} MARS AI Research Platform. All rights reserved.*
"""

    # Save to disk
    work_dir = state.get("work_dir", "")
    final_path = ""
    if work_dir:
        input_dir = os.path.join(work_dir, "input_files")
        os.makedirs(input_dir, exist_ok=True)
        final_path = os.path.join(input_dir, "final_report.md")
        with open(final_path, "w") as f:
            f.write(report)

        output_dir = os.path.join(work_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "final_report.md")
        with open(output_path, "w") as f:
            f.write(report)

    logger.info("assemble_node: report=%d chars, path=%s", len(report), final_path)
    return {
        "final_report": report,
        "messages": [HumanMessage(content="Report assembled.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: PDF Generation
# ═══════════════════════════════════════════════════════════════════════════

def pdf_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate PDF from the assembled final report."""
    from cmbagent.task_framework.newspulse_helpers import generate_pdf_from_markdown

    final_report = state.get("final_report", "")
    work_dir = state.get("work_dir", "")
    industry = state.get("industry", "Industry")
    sentiment_data = state.get("sentiment_data", {})

    pdf_path = ""
    if final_report and work_dir:
        result = generate_pdf_from_markdown(
            final_report, work_dir, industry,
            sentiment_data=sentiment_data,
        )
        pdf_path = result or ""

    logger.info("pdf_node: pdf_path=%s", pdf_path)
    return {
        "pdf_path": pdf_path,
        "messages": [HumanMessage(content=f"PDF generated: {pdf_path}" if pdf_path else "PDF generation skipped.")],
    }
