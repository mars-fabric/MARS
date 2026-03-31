"""
Token counting and capacity management for RFP phases.

Provides:
- Model → max context token limits registry
- Token counting via tiktoken (with fallback estimation)
- Prompt chunking for cases where total tokens exceed model capacity
"""

import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model token capacity registry
#
# Maps model name prefixes/exact names to (max_context_tokens, max_output_tokens).
# When the user selects a model, we look up its capacity to decide whether
# the prompt needs to be broken into sub-parts.
# ---------------------------------------------------------------------------
MODEL_TOKEN_LIMITS: Dict[str, Tuple[int, int]] = {
    # OpenAI models
    "gpt-4o":                   (128_000, 16_384),
    "gpt-4o-mini":              (128_000, 16_384),
    "gpt-4o-mini-2024-07-18":   (128_000, 16_384),
    "gpt-4.1":                  (1_000_000, 32_768),
    "gpt-4.1-2025-04-14":      (1_000_000, 32_768),
    "gpt-4.1-mini":             (1_000_000, 32_768),
    "gpt-5.3":                  (1_000_000, 32_768),
    "o3-mini":                  (128_000, 16_384),
    "o3-mini-2025-01-31":       (128_000, 16_384),
    # Anthropic
    "claude-sonnet-4-20250514": (200_000, 8_192),
    "claude-3.5-sonnet-20241022": (200_000, 8_192),
    # Google Gemini
    "gemini-2.5-pro":           (1_000_000, 8_192),
    "gemini-2.5-flash":         (1_000_000, 8_192),
}

# Fallback when model is not in registry
DEFAULT_CONTEXT_LIMIT = 128_000
DEFAULT_OUTPUT_LIMIT = 16_384


def get_model_limits(model: str) -> Tuple[int, int]:
    """
    Return (max_context_tokens, max_output_tokens) for the given model.

    Tries exact match first, then prefix match, then falls back to defaults.
    """
    # Exact match
    if model in MODEL_TOKEN_LIMITS:
        return MODEL_TOKEN_LIMITS[model]
    # Prefix match (e.g. "gpt-4o-2024-08-06" matches "gpt-4o")
    for prefix, limits in sorted(MODEL_TOKEN_LIMITS.items(), key=lambda x: -len(x[0])):
        if model.startswith(prefix):
            return limits
    logger.warning("Unknown model '%s' — using default token limits (%d ctx, %d out)",
                    model, DEFAULT_CONTEXT_LIMIT, DEFAULT_OUTPUT_LIMIT)
    return (DEFAULT_CONTEXT_LIMIT, DEFAULT_OUTPUT_LIMIT)


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Count tokens in *text* using tiktoken (for OpenAI models) or a
    character-based heuristic for others.
    """
    try:
        import tiktoken
        # tiktoken only knows OpenAI encodings
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")  # safe fallback
        return len(enc.encode(text))
    except ImportError:
        # ~4 chars per token heuristic
        return len(text) // 4


def count_messages_tokens(messages: List[Dict[str, str]], model: str = "gpt-4o") -> int:
    """
    Estimate total tokens for a list of chat messages.
    Each message has overhead (~4 tokens for role/delimiters).
    """
    total = 0
    for msg in messages:
        total += 4  # role + delimiters overhead
        total += count_tokens(msg.get("content", ""), model)
    total += 2  # priming tokens
    return total


# ---------------------------------------------------------------------------
# Prompt chunking
# ---------------------------------------------------------------------------

_SECTION_SEPARATOR = "\n---\n"


def _split_sections(text: str) -> List[str]:
    """
    Split a user prompt at '---' section boundaries.
    Returns a list of text chunks (each with its separator included).
    """
    parts = text.split(_SECTION_SEPARATOR)
    # Re-attach the separator to the end of each chunk (except last)
    chunks = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            chunks.append(part + _SECTION_SEPARATOR)
        else:
            chunks.append(part)
    return chunks


def chunk_prompt_if_needed(
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_completion_tokens: int,
    safety_margin: float = 0.90,
) -> Optional[List[str]]:
    """
    Check whether the prompt fits within the model's context window.

    If it fits, return None (no chunking needed).
    If it doesn't fit, split the user_prompt at section boundaries into
    multiple sub-prompts that each fit within the model's capacity.

    Args:
        system_prompt: The system message content.
        user_prompt: The full user message content.
        model: Model identifier (used for token counting and limit lookup).
        max_completion_tokens: Tokens reserved for the model's output.
        safety_margin: Fraction of context window to actually use (0.90 = 90%).

    Returns:
        None if the prompt fits within limits.
        List[str] of user-prompt sub-chunks if chunking is needed.
    """
    max_ctx, _ = get_model_limits(model)
    usable_ctx = int(max_ctx * safety_margin) - max_completion_tokens

    system_tokens = count_tokens(system_prompt, model)
    user_tokens = count_tokens(user_prompt, model)
    total_prompt_tokens = system_tokens + user_tokens + 6  # message overhead

    logger.info(
        "Token budget check for model=%s: system=%d, user=%d, total=%d, usable_ctx=%d",
        model, system_tokens, user_tokens, total_prompt_tokens, usable_ctx,
    )

    if total_prompt_tokens <= usable_ctx:
        return None  # fits fine

    logger.warning(
        "Prompt exceeds token capacity (%d > %d) — will chunk the prompt.",
        total_prompt_tokens, usable_ctx,
    )

    # Determine how many tokens we can spend on user content per chunk
    per_chunk_budget = usable_ctx - system_tokens - 10  # overhead
    if per_chunk_budget < 2000:
        # System prompt alone nearly fills the context.  Return the entire
        # user prompt as a single chunk so the caller still processes it
        # via the chunked path (logging + guards) instead of silently
        # sending an oversized prompt to the API.
        logger.error("System prompt alone is %d tokens; not enough room for user content.", system_tokens)
        return [user_prompt]

    # Split at section boundaries
    sections = _split_sections(user_prompt)
    if len(sections) <= 1:
        # No section boundaries to split on — return as a single chunk so
        # the caller knows overflow occurred and can log it, rather than
        # silently sending an oversized prompt.
        return [user_prompt]

    # Greedily pack sections into chunks
    chunks: List[str] = []
    current_chunk = ""
    current_tokens = 0

    for section in sections:
        section_tokens = count_tokens(section, model)
        if current_tokens + section_tokens <= per_chunk_budget:
            current_chunk += section
            current_tokens += section_tokens
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # Start new chunk.  If a single section > budget, include it
            # alone (the API may truncate, but it's better than losing it).
            current_chunk = section
            current_tokens = section_tokens

    if current_chunk:
        chunks.append(current_chunk)

    logger.info("Split prompt into %d chunks (section boundaries: %d)", len(chunks), len(sections))
    return chunks


# ---------------------------------------------------------------------------
# Source grouping for divide-and-accumulate strategy
# ---------------------------------------------------------------------------

def group_sources_by_budget(
    sources: Dict[str, str],
    base_prompt_tokens: int,
    model: str,
    max_completion_tokens: int,
    safety_margin: float = 0.90,
) -> List[List[str]]:
    """
    Group source section keys into batches that fit the model's context window.

    Each batch can be sent as a single LLM call along with the base prompt
    (system + document-structure instructions).  Sources are never split or
    truncated — they are assigned whole to a batch.

    Args:
        sources: dict mapping source key → source text.
        base_prompt_tokens: tokens used by system prompt + document structure
                            instructions (everything except the source sections).
        model: model id for token counting and limit lookup.
        max_completion_tokens: tokens reserved for the model's output.
        safety_margin: fraction of context window to actually use (0.90 = 90%).

    Returns:
        List of groups, where each group is a list of source keys that fit
        within one API call.  If all sources fit in one call, returns a single
        group containing all keys.
    """
    max_ctx, _ = get_model_limits(model)
    usable_ctx = int(max_ctx * safety_margin) - max_completion_tokens
    budget = usable_ctx - base_prompt_tokens - 20  # overhead

    if budget < 2000:
        logger.error(
            "Base prompt alone (%d tokens) nearly fills the context (%d usable). "
            "Cannot group sources.", base_prompt_tokens, usable_ctx,
        )
        return [list(sources.keys())]  # single group, let the API try

    # Measure each source
    source_tokens = {k: count_tokens(v, model) for k, v in sources.items()}

    groups: List[List[str]] = []
    current_group: List[str] = []
    current_tokens = 0

    for key in sources:
        tok = source_tokens[key]
        if current_tokens + tok <= budget:
            current_group.append(key)
            current_tokens += tok
        else:
            if current_group:
                groups.append(current_group)
            # Start new group — include this source even if it alone exceeds budget
            current_group = [key]
            current_tokens = tok

    if current_group:
        groups.append(current_group)

    logger.info(
        "Grouped %d sources into %d batches (budget=%d tokens/batch): %s",
        len(sources), len(groups), budget,
        [f"{g} ({sum(source_tokens[k] for k in g):,}tok)" for g in groups],
    )
    return groups
