"""
LangGraph state definition for NewsPulse final report pipeline.

Each node produces one report section independently, avoiding the
context-length explosion that occurs with multi-turn conversation
approaches.
"""

from typing import Optional
from typing_extensions import TypedDict, Annotated, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class NewsPulseReportState(TypedDict):
    """State flowing through the NewsPulse report LangGraph."""

    messages: Annotated[list[AnyMessage], add_messages]

    # ── Input context (set by preprocess) ──
    industry: str
    companies: str
    region: str
    time_window: str
    time_window_human: str
    news_collection: str       # full text from stage 2
    deep_analysis: str         # full text from stage 3
    news_summary: str          # truncated / summarised for per-section prompts
    analysis_summary: str      # truncated / summarised for per-section prompts

    # ── Per-section outputs (populated by nodes) ──
    executive_summary: str
    sentiment_dashboard: str
    sentiment_data: dict          # structured scores for chart rendering
    headlines: str
    in_depth_analysis: str
    company_analysis: str
    trends_opportunities: str
    risks_challenges: str
    regional_dynamics: str
    outlook_recommendations: str
    sources_references: str

    # ── Final assembly ──
    final_report: str
    pdf_path: str

    # ── Config ──
    llm_model: str
    llm_temperature: float
    work_dir: str
