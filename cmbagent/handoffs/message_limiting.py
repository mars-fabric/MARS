"""
Message history limiting.

Applies message history limits to prevent context overflow.

Uses SafeMessageHistoryLimiter which completely replaces the autogen
``MessageHistoryLimiter`` algorithm with a tool-chain-aware truncation
that:
  * never returns an empty list,
  * never splits a ``tool_calls`` ↔ ``tool`` response pair,
  * strips orphaned ``tool`` / ``tool_calls`` after truncation.

Fixes addressed:
1. Autogen ``MessageHistoryLimiter(max_messages=1)`` drops **all** messages
   when the last one carries ``role == "tool"`` → ``IndexError`` crash.
2. After truncation, ``role="tool"`` messages can appear without the
   preceding ``tool_calls`` assistant message → Azure/OpenAI 400 error.
3. After truncation, ``assistant`` messages with ``tool_calls`` can lack
   the corresponding ``role="tool"`` responses → Azure/OpenAI 400 error.
"""

import re
from typing import Dict, List, Any
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import MessageHistoryLimiter
from .debug import debug_print


# ---------------------------------------------------------------------------
# Per-message content truncator  — keeps any single tool result / assistant
# reply from dominating the entire context window.
# ---------------------------------------------------------------------------
_MAX_MSG_CONTENT_CHARS = 25_000      # ≈ 6 k tokens per message — enough for research content
_DIR_BLACKLIST_FRAGMENTS = (
    '.venv', 'venv/', '__pycache__', 'node_modules/', '.git/',
    '.tox/', '.mypy_cache', '.pytest_cache', '/dist/', '/build/',
    '.eggs', '.egg-info', '.cache/', '.npm/', '.yarn/',
    'site-packages/',
)


class MessageContentTruncator:
    """AG2 message transform that caps individual message content.

    Applied *before* other transforms so that downstream limiters work
    on already-reasonable sizes.  Particularly important for tool-role
    messages whose content is the raw return value of external tools
    (e.g. ``DirectoryReadTool`` dumping .venv).
    """

    def __init__(self, max_chars: int = _MAX_MSG_CONTENT_CHARS):
        self._max = max_chars

    # ---- AG2 transform interface ----
    def apply_transform(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                role = msg.get("role", "")
                # Always filter directory noise from tool outputs
                if role == "tool":
                    content = self._filter_dir_noise(content)
                    # Collapse consecutive blank lines (common in scraped HTML)
                    content = re.sub(r'\n{4,}', '\n\n\n', content)
                if len(content) > self._max:
                    content = self._truncate(content, role)
                if content is not msg.get("content"):
                    msg = {**msg, "content": content}
            out.append(msg)
        return out

    def get_logs(self, pre_transform_messages, post_transform_messages):
        """Required by AG2 TransformMessages interface."""
        return {}, False

    # ---- helpers ----
    def _truncate(self, text: str, role: str) -> str:
        head = int(self._max * 0.70)   # 70 % head — keeps abstracts, findings, key data
        tail = self._max - head         # 30 % tail — keeps conclusions, final answers
        return (
            text[:head]
            + f"\n\n... [content truncated: {len(text)} → {self._max} chars] ...\n\n"
            + text[-tail:]
        )

    @staticmethod
    def _filter_dir_noise(text: str) -> str:
        """Remove lines referencing virtual-env / node_modules paths."""
        lines = text.splitlines()
        filtered = [
            l for l in lines
            if not any(bl in l.lower() for bl in _DIR_BLACKLIST_FRAGMENTS)
        ]
        # Only bother if we actually removed something
        if len(filtered) < len(lines):
            return "\n".join(filtered)
        return text


class SafeMessageHistoryLimiter(MessageHistoryLimiter):
    """MessageHistoryLimiter with tool-chain-aware truncation.

    The autogen base class has a flaw: its truncation loop skips ``tool``
    messages in the "last slot", silently producing fewer messages than
    ``max_messages`` and breaking tool call/response integrity.

    This subclass **overrides** ``apply_transform`` entirely:

    1. Group consecutive ``assistant(tool_calls) → tool(response)*``
       sequences into atomic *chains* that are never split.
    2. Walk from the end of the conversation, accumulating chains /
       messages until the budget is exhausted.
    3. Sanitise any remaining orphans (should not happen, but defence in
       depth).
    4. Guarantee at least one message is always returned.
    """

    def apply_transform(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self._max_messages is None or len(messages) <= self._max_messages:
            return list(messages)

        # ---- build atomic groups ----
        groups = self._build_groups(messages)

        # ---- collect from end until budget is met ----
        budget = self._max_messages
        selected: List[List[Dict[str, Any]]] = []

        for grp in reversed(groups):
            if budget <= 0:
                break
            selected.append(grp)
            budget -= len(grp)

        # Flatten back into a single ordered list
        selected.reverse()
        result: List[Dict[str, Any]] = []
        for grp in selected:
            result.extend(grp)

        # ---- safety: sanitise any remaining orphans ----
        result = self._sanitise_tool_chain(result)

        # ---- guarantee non-empty ----
        if not result and messages:
            for msg in reversed(messages):
                if msg.get("role") != "tool":
                    return [msg]
            return [messages[-1]]

        return result

    # ------------------------------------------------------------------
    # Grouping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_groups(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Partition messages into atomic groups.

        An *assistant+tool chain* is an ``assistant`` message that has
        ``tool_calls``, followed by one or more ``role="tool"`` messages
        whose ``tool_call_id`` matches one of the calls.  Such a
        sequence is treated as a single indivisible group.

        All other messages become single-element groups.
        """
        groups: List[List[Dict[str, Any]]] = []
        i = 0
        n = len(messages)

        while i < n:
            msg = messages[i]
            # Detect assistant with tool_calls
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                call_ids = {c.get("id") for c in msg["tool_calls"] if c.get("id")}
                chain = [msg]
                j = i + 1
                while j < n and messages[j].get("role") == "tool":
                    tid = messages[j].get("tool_call_id")
                    if tid in call_ids:
                        chain.append(messages[j])
                    else:
                        break  # tool response for a different chain
                    j += 1
                groups.append(chain)
                i = j
            else:
                groups.append([msg])
                i += 1

        return groups

    # ------------------------------------------------------------------
    # Sanitisation (defence in depth — should rarely fire)
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitise_tool_chain(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Make tool / tool_calls relationships API-valid.

        1. Build a set of ``tool_call_id`` values present in
           ``role="tool"`` messages.
        2. For every ``assistant`` message with ``tool_calls``, check
           whether **all** referenced ids have responses.  If not, strip
           ``tool_calls`` (and drop the message if it becomes empty).
        3. Remove ``role="tool"`` messages whose ``tool_call_id`` is not
           referenced by any remaining ``assistant`` ``tool_calls``.
        """

        # --- Pass 1: collect tool_call_ids that have responses ----------
        response_ids: set = set()
        for msg in messages:
            if msg.get("role") == "tool":
                tid = msg.get("tool_call_id")
                if tid:
                    response_ids.add(tid)

        # --- Pass 2: fix assistant messages with orphaned tool_calls ----
        cleaned: List[Dict[str, Any]] = []
        surviving_call_ids: set = set()

        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                calls = msg["tool_calls"]
                valid_calls = [c for c in calls if c.get("id") in response_ids]
                if valid_calls:
                    new_msg = {**msg, "tool_calls": valid_calls}
                    cleaned.append(new_msg)
                    surviving_call_ids.update(c["id"] for c in valid_calls)
                else:
                    content = msg.get("content")
                    if content:
                        new_msg = {k: v for k, v in msg.items() if k != "tool_calls"}
                        cleaned.append(new_msg)
            else:
                cleaned.append(msg)

        # --- Pass 3: remove orphaned tool responses ---------------------
        final: List[Dict[str, Any]] = []
        for msg in cleaned:
            if msg.get("role") == "tool":
                tid = msg.get("tool_call_id")
                if tid and tid in surviving_call_ids:
                    final.append(msg)
            else:
                final.append(msg)

        return final


def apply_message_history_limiting(agents: Dict):
    """
    Apply message history limiting to response formatters.

    This prevents context overflow by limiting message history.
    Uses SafeMessageHistoryLimiter to avoid the empty-list edge case
    that crashes autogen when the conversation contains tool-role messages.

    Args:
        agents: Dictionary of agent instances
    """
    debug_print('Applying message history limiting...')

    # ------------------------------------------------------------------
    # 1. Per-message content truncator — applied to EVERY agent so that
    #    no single tool output or assistant reply can dominate context.
    #    We iterate all agents in the dict rather than a hardcoded list
    #    so newly added agents are automatically covered.
    # ------------------------------------------------------------------
    content_truncator = TransformMessages(
        transforms=[MessageContentTruncator(max_chars=_MAX_MSG_CONTENT_CHARS)]
    )

    applied_content = 0
    for agent_name, agent_obj in agents.items():
        try:
            content_truncator.add_to_agent(agent_obj.agent)
            applied_content += 1
        except Exception:
            pass  # some agents may not support transforms

    debug_print(f'Applied content truncator to {applied_content}/{len(agents)} agents\n', indent=2)

    # ------------------------------------------------------------------
    # 2. Message-count limiter for agents that tend to accumulate long
    #    chat histories (give generous budget of 30 messages for core
    #    agents — enough for multi-turn tool use within a step).
    # ------------------------------------------------------------------
    core_history_limit = TransformMessages(
        transforms=[SafeMessageHistoryLimiter(max_messages=30)]
    )

    history_limit_agents = [
        'engineer', 'researcher', 'executor',
        'web_surfer', 'retrieve_assistant',
        'idea_maker', 'idea_hater',
    ]

    applied_history = 0
    for agent_name in history_limit_agents:
        if agent_name in agents:
            try:
                core_history_limit.add_to_agent(agents[agent_name].agent)
                applied_history += 1
            except Exception:
                pass

    debug_print(f'Applied history limiter (30 msgs) to {applied_history} core agents\n', indent=2)

    # ------------------------------------------------------------------
    # 3. Tight limiter for response formatters (only need last few msgs)
    # ------------------------------------------------------------------

    # Use max_messages=3 for general formatters – gives enough buffer
    # for retry scenarios where tool-role messages accumulate.
    context_handling = TransformMessages(
        transforms=[SafeMessageHistoryLimiter(max_messages=3)]
    )

    # executor_response_formatter needs more context to see exitcode
    executor_formatter_handling = TransformMessages(
        transforms=[SafeMessageHistoryLimiter(max_messages=3)]
    )
    if 'executor_response_formatter' in agents:
        executor_formatter_handling.add_to_agent(agents['executor_response_formatter'].agent)

    # Apply to response formatters (they only need recent context)
    formatter_agents = [
        'planner_response_formatter',
        'plan_recorder',
        'reviewer_response_formatter',
        'review_recorder',
        'researcher_response_formatter',
        'researcher_executor',
        'idea_maker_response_formatter',
        'idea_hater_response_formatter',
        'summarizer_response_formatter',
    ]

    for agent_name in formatter_agents:
        if agent_name in agents:
            context_handling.add_to_agent(agents[agent_name].agent)

    debug_print(f'Applied formatter limiter (3 msgs) to {len([a for a in formatter_agents if a in agents])} agents\n', indent=2)
