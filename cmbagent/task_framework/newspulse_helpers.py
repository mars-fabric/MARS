"""
Stage-specific helpers for the Industry News & Sentiment Pulse pipeline.

Stages:
  1 — Setup & Configuration (no AI — stores request + model config)
  2 — News Discovery & Collection (AI research via DDGS — headlines, raw data)
  3 — Deep Sentiment & Analysis (AI research via DDGS — analysis, trends, risks)
  4 — Final Report + PDF (AI compilation into 12-section report + PDF)

Each AI stage (2, 3, 4) supports HITL review between stages.
Model configuration follows the Deep Research pattern.
"""

import os
import re
import logging
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ─── Default model assignments — loaded from model_config.yaml via registry ──

def _get_discovery_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_stage_defaults("newspulse", 2)


def _get_analysis_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_stage_defaults("newspulse", 3)


def _get_final_report_defaults() -> dict:
    from cmbagent.config.model_registry import get_model_registry
    return get_model_registry().get_stage_defaults("newspulse", 4)


TIME_WINDOW_LABELS = {
    "1d": "the past 24 hours",
    "7d": "the past week",
    "30d": "the past month",
    "90d": "the past 3 months",
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


def _compute_year_scope(time_window: str) -> str:
    """Extract the target year(s) from a time_window value for search queries."""
    import re
    now = datetime.now()

    # If the time_window is a pure year like "2025", "2026"
    if re.match(r'^\d{4}$', time_window.strip()):
        return time_window.strip()

    # If it contains a year range like "2025-2026"
    m = re.match(r'^(\d{4})\s*[-–]\s*(\d{4})$', time_window.strip())
    if m:
        return f"{m.group(1)} {m.group(2)}"

    # If it contains a quarter like "Q1 2025"
    m = re.search(r'Q[1-4]\s*(\d{4})', time_window)
    if m:
        return m.group(1)

    # If it contains a half like "H1 2025"
    m = re.search(r'H[12]\s*(\d{4})', time_window)
    if m:
        return m.group(1)

    # Short codes: guess from current year
    if time_window in ("1d", "7d", "30d"):
        return str(now.year)
    if time_window == "90d":
        # Could span two years near Jan
        if now.month <= 3:
            return f"{now.year - 1} {now.year}"
        return str(now.year)

    # Fallback: extract any 4-digit year from the string
    years = re.findall(r'\b(20\d{2})\b', time_window)
    if years:
        return " ".join(sorted(set(years)))

    return str(now.year)


def _compute_exclusion_years(year_scope: str) -> str:
    """Build a human-readable list of years to exclude."""
    import re
    now = datetime.now()
    scope_years = set(re.findall(r'\b(20\d{2})\b', year_scope))
    scope_ints = {int(y) for y in scope_years} if scope_years else {now.year}

    # Build exclusion list: common years users might accidentally get
    all_recent = set(range(2020, now.year + 2))
    excluded = sorted(all_recent - scope_ints)
    if not excluded:
        return "years before 2024"
    return ", ".join(str(y) for y in excluded)


# ═══════════════════════════════════════════════════════════════════════════
# Stage 1 — Setup & Configuration (no AI)
# ═══════════════════════════════════════════════════════════════════════════

def build_user_input_output(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
) -> dict:
    """Build output_data for stage 1 (user input + config capture)."""
    return {
        "shared": {
            "industry": industry,
            "companies": companies or "",
            "region": region or "Global",
            "time_window": time_window or "7d",
            "user_input_summary": (
                f"Industry: {industry}\n"
                f"Companies: {companies or 'None specified'}\n"
                f"Region: {region or 'Global'}\n"
                f"Time Window: {time_window or '7d'}"
            ),
        },
        "artifacts": {},
        "chat_history": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — News Discovery & Collection (DDGS Research)
# ═══════════════════════════════════════════════════════════════════════════

def build_discovery_kwargs(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (news discovery)."""
    from cmbagent.task_framework.prompts.newspulse.discovery import (
        discovery_planner_prompt,
        discovery_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir

    cfg = {**_get_discovery_defaults(), **(config_overrides or {})}
    discovery_dir = create_work_dir(work_dir, "discovery")
    time_window_human = TIME_WINDOW_LABELS.get(time_window, time_window)
    year_scope = _compute_year_scope(time_window)
    exclusion_years = _compute_exclusion_years(year_scope)

    task_desc = (
        f"Search and collect the latest news, breaking stories, and major "
        f"developments in the {industry} industry for the {region} region "
        f"over {time_window_human} (year: {year_scope}). Use web search "
        f"extensively to gather real, current data from multiple sources. "
        f"IMPORTANT: Every search query must include '{year_scope}' and '{region}'. "
        f"Discard any result from {exclusion_years}."
    )
    if companies:
        task_desc += f" Include focused searches on: {companies}."

    fmt_kwargs = dict(
        industry=industry,
        company=companies or "None specified",
        companies=companies or "None specified",
        region=region,
        time_window=time_window,
        time_window_human=time_window_human,
        year_scope=year_scope,
        exclusion_years=exclusion_years,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=6,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=discovery_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=discovery_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(discovery_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="news_discovery",
        callbacks=callbacks,
    )


def extract_stage_result(results: dict) -> str:
    """Extract the report content from chat_history (shared by stages 2/3/4)."""
    from cmbagent.task_framework.utils import get_task_result, extract_clean_markdown

    chat_history = results["chat_history"]

    task_result = ""
    for agent_name in ("researcher", "researcher_response_formatter"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: pick longest non-empty message
    if not task_result:
        logger.warning("Primary extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        raise ValueError(
            f"No report content found in chat history. Available agents: {list(set(agent_names))}"
        )

    return extract_clean_markdown(task_result)


def save_stage_file(content: str, work_dir: str, filename: str) -> str:
    """Write a stage output file to input_files/ and return the path."""
    input_dir = os.path.join(str(work_dir), "input_files")
    os.makedirs(input_dir, exist_ok=True)
    path = os.path.join(input_dir, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def build_discovery_output(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    news_collection: str,
    file_path: str,
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (news discovery stage)."""
    return {
        "shared": {
            "industry": industry,
            "companies": companies,
            "region": region,
            "time_window": time_window,
            "news_collection": news_collection,
        },
        "artifacts": {
            "news_collection.md": file_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Deep Sentiment & Analysis (DDGS Research)
# ═══════════════════════════════════════════════════════════════════════════

def build_analysis_kwargs(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    news_collection: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (deep analysis)."""
    from cmbagent.task_framework.prompts.newspulse.analysis import (
        analysis_planner_prompt,
        analysis_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir

    cfg = {**_get_analysis_defaults(), **(config_overrides or {})}
    analysis_dir = create_work_dir(work_dir, "analysis")
    time_window_human = TIME_WINDOW_LABELS.get(time_window, time_window)
    year_scope = _compute_year_scope(time_window)
    exclusion_years = _compute_exclusion_years(year_scope)

    task_desc = (
        f"Perform deep sentiment analysis, trend identification, risk assessment, "
        f"and company analysis for the {industry} industry in {region} "
        f"during {time_window_human} ({year_scope}). "
        f"Build on the collected news data and perform additional web searches "
        f"to create comprehensive analytical insights. "
        f"IMPORTANT: Every search query must include '{year_scope}' and '{region}'. "
        f"Discard any data from {exclusion_years}."
    )
    if companies:
        task_desc += f" Provide detailed analysis for: {companies}."

    fmt_kwargs = dict(
        industry=industry,
        company=companies or "None specified",
        companies=companies or "None specified",
        region=region,
        time_window=time_window,
        time_window_human=time_window_human,
        year_scope=year_scope,
        exclusion_years=exclusion_years,
        news_collection=news_collection,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=8,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=analysis_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=analysis_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(analysis_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="deep_analysis",
        callbacks=callbacks,
    )


def build_analysis_output(
    shared_state: dict,
    deep_analysis: str,
    file_path: str,
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (deep analysis stage)."""
    return {
        "shared": {
            **shared_state,
            "deep_analysis": deep_analysis,
        },
        "artifacts": {
            "deep_analysis.md": file_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4 — Final Report + PDF Build
# ═══════════════════════════════════════════════════════════════════════════

def build_final_report_kwargs(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    news_collection: str,
    deep_analysis: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (final report)."""
    from cmbagent.task_framework.prompts.newspulse.final_report import (
        final_report_planner_prompt,
        final_report_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir

    cfg = {**_get_final_report_defaults(), **(config_overrides or {})}
    final_dir = create_work_dir(work_dir, "final_report")
    time_window_human = TIME_WINDOW_LABELS.get(time_window, time_window)
    year_scope = _compute_year_scope(time_window)
    exclusion_years = _compute_exclusion_years(year_scope)

    task_desc = (
        f"Produce the final executive Industry News & Sentiment Pulse report "
        f"for the {industry} industry in {region} over {time_window_human} "
        f"({year_scope}). Compile all research and analysis into a polished, "
        f"publication-ready report with standardized sections. "
        f"All data must be from {year_scope} and focused on {region}. "
        f"Perform final verification searches (include '{year_scope} {region}' in queries)."
    )

    fmt_kwargs = dict(
        industry=industry,
        company=companies or "None specified",
        companies=companies or "None specified",
        region=region,
        time_window=time_window,
        time_window_human=time_window_human,
        year_scope=year_scope,
        exclusion_years=exclusion_years,
        news_collection=news_collection,
        deep_analysis=deep_analysis,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=6,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=final_report_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=final_report_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(final_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="final_report",
        callbacks=callbacks,
    )


def build_final_report_output(
    shared_state: dict,
    final_report: str,
    final_report_path: str,
    pdf_path: Optional[str],
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (final report stage)."""
    artifacts = {"final_report.md": final_report_path}
    if pdf_path:
        artifacts["report.pdf"] = pdf_path

    return {
        "shared": {
            **shared_state,
            "final_report": final_report,
        },
        "artifacts": artifacts,
        "chat_history": chat_history,
    }


def generate_pdf_from_markdown(
    markdown_content: str,
    work_dir: str,
    industry: str,
    sentiment_data: dict | None = None,
) -> Optional[str]:
    """Convert a markdown report to PDF.

    Uses markdown → HTML → PDF conversion via weasyprint (if available),
    falls back to a simple text-based approach.

    Args:
        markdown_content: Full markdown report text.
        work_dir: Working directory for output files.
        industry: Industry name for the report title.
        sentiment_data: Optional structured sentiment dict for chart rendering.
    """
    output_dir = os.path.join(str(work_dir), "output")
    os.makedirs(output_dir, exist_ok=True)

    safe_name = re.sub(r'[^\w\s-]', '', industry).strip().replace(' ', '_')
    pdf_filename = f"news_sentiment_pulse_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)

    # Generate chart images if we have sentiment data and matplotlib
    chart_paths = {}
    if sentiment_data:
        try:
            chart_paths = _generate_sentiment_charts(sentiment_data, output_dir)
            logger.info("Generated %d chart images for PDF", len(chart_paths))
        except Exception as e:
            logger.warning("Chart generation failed (continuing without charts): %s", e)

    try:
        from weasyprint import HTML
        html_content = _markdown_to_html(markdown_content, industry, sentiment_data, chart_paths)
        HTML(string=html_content, base_url=output_dir).write_pdf(pdf_path)
        logger.info("PDF generated via weasyprint: %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.info("weasyprint not available, trying fpdf2")

    try:
        from fpdf import FPDF

        # ── Unicode sanitization for latin-1 ──
        _unicode_replacements = {
            '\u2014': '--',   # em dash
            '\u2013': '-',    # en dash
            '\u2018': "'",    # left single quote
            '\u2019': "'",    # right single quote
            '\u201c': '"',    # left double quote
            '\u201d': '"',    # right double quote
            '\u2026': '...',  # ellipsis
            '\u2022': '*',    # bullet
            '\u00a0': ' ',    # non-breaking space
            '\u200b': '',     # zero-width space
            '\U0001f7e1': '[Y]',  # yellow circle
            '\U0001f7e2': '[G]',  # green circle
            '\U0001f534': '[R]',  # red circle
            '\U0001f4c8': '^',    # chart increasing
            '\u27a1\ufe0f': '->',  # right arrow with variant
            '\u27a1': '->',        # right arrow
            '\u2197\ufe0f': '^',   # north-east arrow
            '\u2198\ufe0f': 'v',   # south-east arrow
        }

        def _sanitize_for_latin1(text: str) -> str:
            for char, replacement in _unicode_replacements.items():
                text = text.replace(char, replacement)
            return text.encode('latin-1', errors='replace').decode('latin-1')

        def _strip_md_formatting(text: str) -> str:
            """Strip markdown inline formatting to plain text."""
            # Remove HTML comments
            text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
            # Convert markdown links [text](url) -> text (url)
            text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
            # Remove bold+italic (***text*** or ___text___)
            text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
            text = re.sub(r'_{3}(.+?)_{3}', r'\1', text)
            # Remove bold (**text** or __text__)
            text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
            text = re.sub(r'_{2}(.+?)_{2}', r'\1', text)
            # Remove italic (*text* or _text_) — careful with bullet lists
            text = re.sub(r'(?<!\w)\*([^*\n]+?)\*(?!\w)', r'\1', text)
            text = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'\1', text)
            # Remove backtick code
            text = re.sub(r'`([^`]*)`', r'\1', text)
            return text.strip()

        markdown_content = _sanitize_for_latin1(markdown_content)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title block
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 12, "Industry News & Sentiment Pulse", ln=True, align="C")
        pdf.set_font("Helvetica", "", 13)
        pdf.cell(0, 8, industry, ln=True, align="C")
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, f"Executive Intelligence Report  |  {datetime.now().strftime('%B %d, %Y')}", ln=True, align="C")
        pdf.ln(4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        in_html_comment = False
        in_blockquote = False
        blockquote_lines: list[str] = []
        # Track table state for proper rendering
        in_table = False
        table_rows: list[list[str]] = []
        table_col_count = 0

        def _flush_blockquote():
            nonlocal in_blockquote, blockquote_lines
            if blockquote_lines:
                pdf.set_fill_color(240, 244, 250)
                pdf.set_draw_color(30, 64, 175)
                x = pdf.get_x()
                y = pdf.get_y()
                # Draw left border
                bq_text = "\n".join(blockquote_lines)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_x(x + 6)
                pdf.multi_cell(170, 5, _strip_md_formatting(bq_text), fill=True)
                pdf.ln(2)
                blockquote_lines = []
            in_blockquote = False

        def _flush_table():
            nonlocal in_table, table_rows, table_col_count
            if not table_rows:
                in_table = False
                return
            # Calculate column widths
            page_w = 190
            col_w = page_w / max(table_col_count, 1)
            for row_idx, cells in enumerate(table_rows):
                if row_idx == 0:
                    # Header row
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_fill_color(30, 64, 175)
                    pdf.set_text_color(255, 255, 255)
                    for cell in cells:
                        pdf.cell(col_w, 6, _strip_md_formatting(cell.strip())[:30], border=1, fill=True, align="C")
                    pdf.ln()
                    pdf.set_text_color(0, 0, 0)
                else:
                    # Data rows
                    pdf.set_font("Helvetica", "", 8)
                    fill = row_idx % 2 == 0
                    if fill:
                        pdf.set_fill_color(248, 250, 252)
                    for cell in cells:
                        pdf.cell(col_w, 5, _strip_md_formatting(cell.strip())[:30], border=1, fill=fill)
                    pdf.ln()
            pdf.ln(2)
            table_rows = []
            table_col_count = 0
            in_table = False

        lines = markdown_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            i += 1

            # Skip HTML comments
            if '<!--' in line:
                if '-->' not in line:
                    in_html_comment = True
                continue
            if in_html_comment:
                if '-->' in line:
                    in_html_comment = False
                continue

            # ── Blockquotes ──
            if line.startswith('> '):
                if not in_blockquote:
                    in_blockquote = True
                blockquote_lines.append(line[2:])
                continue
            elif in_blockquote:
                _flush_blockquote()

            # ── Table rows ──
            if line.startswith('|'):
                # Skip separator rows (|---|---|)
                if re.match(r'^\|[\s\-:|]+\|$', line):
                    continue
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if not in_table:
                    in_table = True
                    table_col_count = len(cells)
                table_rows.append(cells)
                continue
            elif in_table:
                _flush_table()

            # ── Horizontal rule ──
            if line.strip() == '---':
                pdf.ln(2)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)
                continue

            # ── Headings ──
            if line.startswith('#### '):
                pdf.set_font("Helvetica", "B", 11)
                pdf.ln(4)
                pdf.multi_cell(0, 6, _strip_md_formatting(line[5:]))
                pdf.ln(1)
                continue
            if line.startswith('### '):
                pdf.set_font("Helvetica", "B", 12)
                pdf.ln(4)
                pdf.multi_cell(0, 6, _strip_md_formatting(line[4:]))
                pdf.ln(1)
                continue
            if line.startswith('## '):
                pdf.ln(3)
                pdf.set_draw_color(30, 64, 175)
                pdf.set_fill_color(30, 64, 175)
                pdf.rect(10, pdf.get_y(), 3, 8, 'F')
                pdf.set_x(16)
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 8, _strip_md_formatting(line[3:]), ln=True)
                pdf.set_draw_color(226, 232, 240)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(3)
                continue
            if line.startswith('# '):
                pdf.set_font("Helvetica", "B", 16)
                pdf.ln(5)
                pdf.multi_cell(0, 9, _strip_md_formatting(line[2:]))
                pdf.set_draw_color(30, 64, 175)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(3)
                continue

            # ── Numbered list ──
            num_match = re.match(r'^(\d+)\.\s+(.+)', line)
            if num_match:
                num = num_match.group(1)
                content = _strip_md_formatting(num_match.group(2))
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(8, 5, f"{num}.")
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, content)
                pdf.ln(1)
                continue

            # ── Bullet list ──
            if line.startswith('- ') or line.startswith('* '):
                content = _strip_md_formatting(line[2:])
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(6, 5, " -")
                pdf.multi_cell(0, 5, content)
                pdf.ln(1)
                continue

            # ── Normal paragraph text ──
            if line.strip():
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, _strip_md_formatting(line))
                continue

            # ── Blank line ──
            pdf.ln(2)

        # Flush any remaining blockquote/table
        if in_blockquote:
            _flush_blockquote()
        if in_table:
            _flush_table()

        # Footer
        pdf.ln(8)
        pdf.set_draw_color(226, 232, 240)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 4, f"Generated by MARS AI Research Platform  |  {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC", ln=True, align="C")
        pdf.cell(0, 4, "All information sourced from publicly available data. Verify independently.", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        pdf.output(pdf_path)
        logger.info("PDF generated via fpdf2: %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.warning("Neither weasyprint nor fpdf2 available for PDF generation")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Chart generation helpers
# ═══════════════════════════════════════════════════════════════════════════

def _generate_sentiment_charts(sentiment_data: dict, output_dir: str) -> dict:
    """Generate matplotlib chart images and return {name: file_path} dict."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    import numpy as np

    chart_paths = {}

    # ── 1. Gauge chart for overall sentiment ──
    try:
        fig, ax = plt.subplots(figsize=(5, 3), subplot_kw={"projection": "polar"})
        overall = sentiment_data.get("overall_sentiment", {})
        score = overall.get("score", 50)

        # Half-circle gauge
        theta = np.linspace(np.pi, 0, 200)
        colors_gradient = plt.cm.RdYlGn(np.linspace(0, 1, 200))

        for i in range(len(theta) - 1):
            ax.bar(theta[i], 1, width=(theta[i] - theta[i+1]),
                   bottom=0.6, color=colors_gradient[i], edgecolor="none")

        # Needle
        needle_angle = np.pi - (score / 100) * np.pi
        ax.plot([needle_angle, needle_angle], [0, 1.5], color="#1a1a2e",
                linewidth=2.5, solid_capstyle="round")
        ax.plot(needle_angle, 1.5, "o", color="#1a1a2e", markersize=4)
        ax.plot(needle_angle, 0, "o", color="#1a1a2e", markersize=8)

        ax.set_ylim(0, 2)
        ax.set_thetamin(0)
        ax.set_thetamax(180)
        ax.set_rticks([])
        ax.set_thetagrids([])
        ax.spines["polar"].set_visible(False)
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")

        # Labels
        ax.text(np.pi, -0.3, "Bearish", ha="center", fontsize=8, color="#e74c3c", fontweight="bold")
        ax.text(np.pi/2, -0.3, "Neutral", ha="center", fontsize=8, color="#f39c12", fontweight="bold")
        ax.text(0, -0.3, "Bullish", ha="center", fontsize=8, color="#27ae60", fontweight="bold")
        ax.text(np.pi/2, -0.7, f"{overall.get('label', 'N/A')} — {score}/100",
                ha="center", fontsize=12, fontweight="bold", color="#1a1a2e")

        plt.tight_layout()
        path = os.path.join(output_dir, "chart_gauge.png")
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        chart_paths["gauge"] = path
    except Exception as e:
        logger.warning("Gauge chart failed: %s", e)

    # ── 2. Horizontal bar chart for all indicators ──
    try:
        indicators = [
            ("Overall Sentiment", sentiment_data.get("overall_sentiment", {}).get("score", 50)),
            ("Industry Momentum", sentiment_data.get("industry_momentum", {}).get("score", 50)),
            ("Investment Activity", sentiment_data.get("investment_activity", {}).get("score", 50)),
            ("Innovation Index", sentiment_data.get("innovation_index", {}).get("score", 50)),
            ("Risk Level", sentiment_data.get("risk_level", {}).get("score", 50)),
        ]
        labels = [i[0] for i in indicators]
        scores = [i[1] for i in indicators]

        fig, ax = plt.subplots(figsize=(7, 3.5))

        # Color gradient based on score
        bar_colors = []
        for s in scores:
            if s >= 70:
                bar_colors.append("#27ae60")
            elif s >= 50:
                bar_colors.append("#f39c12")
            elif s >= 30:
                bar_colors.append("#e67e22")
            else:
                bar_colors.append("#e74c3c")
        # Risk level: invert color logic
        risk_score = scores[-1]
        if risk_score >= 70:
            bar_colors[-1] = "#e74c3c"
        elif risk_score >= 50:
            bar_colors[-1] = "#e67e22"
        elif risk_score >= 30:
            bar_colors[-1] = "#f39c12"
        else:
            bar_colors[-1] = "#27ae60"

        y_pos = range(len(labels))
        bars = ax.barh(y_pos, scores, height=0.6, color=bar_colors,
                       edgecolor="white", linewidth=0.5, zorder=3)

        # Background bars (track)
        ax.barh(y_pos, [100]*len(labels), height=0.6, color="#f0f0f0",
                edgecolor="none", zorder=1)

        # Score labels on bars
        for i, (bar, score) in enumerate(zip(bars, scores)):
            ax.text(score + 2, i, f"{score}", va="center", fontsize=10,
                    fontweight="bold", color="#333")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10, fontweight="500")
        ax.set_xlim(0, 110)
        ax.set_xlabel("Score (0–100)", fontsize=9, color="#666")
        ax.invert_yaxis()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#ddd")
        ax.spines["left"].set_visible(False)
        ax.tick_params(left=False, bottom=True, colors="#999")
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")

        plt.tight_layout()
        path = os.path.join(output_dir, "chart_indicators.png")
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        chart_paths["indicators"] = path
    except Exception as e:
        logger.warning("Indicator bar chart failed: %s", e)

    # ── 3. Donut chart for sentiment distribution ──
    try:
        dist = sentiment_data.get("sentiment_distribution", {})
        sizes = [dist.get("positive", 40), dist.get("neutral", 35), dist.get("negative", 25)]
        labels = ["Positive", "Neutral", "Negative"]
        colors = ["#27ae60", "#f39c12", "#e74c3c"]
        explode = (0.03, 0.03, 0.03)

        fig, ax = plt.subplots(figsize=(4, 4))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, explode=explode,
            autopct="%1.0f%%", startangle=90, pctdistance=0.78,
            wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
            textprops={"fontsize": 10, "fontweight": "500"},
        )
        for t in autotexts:
            t.set_fontsize(11)
            t.set_fontweight("bold")
            t.set_color("white")

        # Center circle decoration
        confidence = sentiment_data.get("confidence_score", 65)
        ax.text(0, 0.08, f"{confidence}%", ha="center", va="center",
                fontsize=22, fontweight="bold", color="#1a1a2e")
        ax.text(0, -0.15, "Confidence", ha="center", va="center",
                fontsize=9, color="#666")

        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")
        plt.tight_layout()
        path = os.path.join(output_dir, "chart_distribution.png")
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        chart_paths["distribution"] = path
    except Exception as e:
        logger.warning("Distribution donut chart failed: %s", e)

    # ── 4. Outlook signal badge ──
    try:
        outlook = sentiment_data.get("outlook_signal", "Hold")
        signal_map = {
            "Strong Buy": ("#27ae60", "⬆⬆"),
            "Buy": ("#2ecc71", "⬆"),
            "Hold": ("#f39c12", "⬌"),
            "Sell": ("#e74c3c", "⬇"),
            "Strong Sell": ("#c0392b", "⬇⬇"),
        }
        color, arrow = signal_map.get(outlook, ("#f39c12", "⬌"))

        fig, ax = plt.subplots(figsize=(3.5, 1.2))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 3)
        ax.axis("off")

        # Badge background
        badge = FancyBboxPatch((0.3, 0.3), 9.4, 2.4, boxstyle="round,pad=0.3",
                               facecolor=color, edgecolor="white", linewidth=2, alpha=0.95)
        ax.add_patch(badge)

        ax.text(5, 1.5, f"OUTLOOK: {outlook.upper()}", ha="center", va="center",
                fontsize=16, fontweight="bold", color="white",
                fontfamily="sans-serif")

        fig.patch.set_facecolor("white")
        plt.tight_layout()
        path = os.path.join(output_dir, "chart_outlook.png")
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        chart_paths["outlook"] = path
    except Exception as e:
        logger.warning("Outlook badge chart failed: %s", e)

    return chart_paths


def _markdown_to_html(
    markdown_content: str,
    industry: str,
    sentiment_data: dict | None = None,
    chart_paths: dict | None = None,
) -> str:
    """Convert markdown to styled HTML for PDF rendering with embedded charts."""
    try:
        import markdown
        body = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code'],
        )
    except ImportError:
        # Fallback: basic conversion
        import html
        body = f"<pre>{html.escape(markdown_content)}</pre>"

    # Build chart HTML to inject into the sentiment dashboard section
    chart_html = _build_chart_html(sentiment_data, chart_paths)

    # Replace the markdown-rendered sentiment dashboard with chart version
    if chart_html:
        import re as _re
        # Find the sentiment dashboard section and inject charts after it
        pattern = r'(<!-- SENTIMENT_DASHBOARD_START -->.*?<!-- SENTIMENT_DASHBOARD_END -->)'
        replacement = chart_html
        body = _re.sub(pattern, replacement, body, flags=_re.DOTALL)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm 2cm;
    @top-center {{
      content: "{industry} — Industry News & Sentiment Pulse";
      font-size: 7.5pt;
      color: #999;
      font-family: 'Helvetica Neue', Arial, sans-serif;
    }}
    @bottom-left {{
      content: "MARS AI Research Platform — Confidential";
      font-size: 7pt;
      color: #bbb;
    }}
    @bottom-right {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 7.5pt;
      color: #999;
    }}
  }}
  body {{
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.7;
    color: #1e293b;
    max-width: 780px;
    margin: 0 auto;
  }}

  /* ── Typography ── */
  h1 {{
    color: #0f172a;
    border-bottom: 3px solid #1e40af;
    padding-bottom: 12px;
    font-size: 22pt;
    letter-spacing: -0.5px;
    margin-top: 0;
    font-weight: 800;
  }}
  h2 {{
    color: #1e40af;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
    margin-top: 32px;
    font-size: 15pt;
    letter-spacing: -0.3px;
    page-break-after: avoid;
    font-weight: 700;
  }}
  h2::before {{
    content: "";
    display: inline-block;
    width: 4px;
    height: 18px;
    background: linear-gradient(180deg, #1e40af, #7c3aed);
    margin-right: 10px;
    vertical-align: middle;
    border-radius: 2px;
  }}
  h3 {{
    color: #7c3aed;
    margin-top: 20px;
    font-size: 12pt;
    page-break-after: avoid;
    font-weight: 600;
  }}
  h4 {{
    color: #334155;
    margin-top: 16px;
    font-size: 11pt;
    page-break-after: avoid;
    font-weight: 600;
  }}
  p {{
    margin: 8px 0;
    text-align: justify;
  }}

  /* ── Tables ── */
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 9.5pt;
    border-radius: 6px;
    overflow: hidden;
  }}
  th, td {{
    border: 1px solid #e2e8f0;
    padding: 10px 14px;
    text-align: left;
  }}
  th {{
    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
    color: white;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 8.5pt;
    letter-spacing: 0.8px;
  }}
  tr:nth-child(even) {{ background-color: #f8fafc; }}
  td:first-child {{ font-weight: 500; }}

  /* ── Lists ── */
  ul, ol {{ margin: 10px 0; padding-left: 24px; }}
  li {{ margin-bottom: 6px; }}

  /* ── Dividers ── */
  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 28px 0;
  }}

  /* ── Blockquotes (used for report metadata) ── */
  blockquote {{
    border-left: 4px solid #1e40af;
    margin: 16px 0;
    padding: 14px 20px;
    background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
    color: #374151;
    font-size: 9.5pt;
    border-radius: 0 6px 6px 0;
  }}
  blockquote strong {{ color: #1e293b; }}

  /* ── Links ── */
  a {{ color: #1e40af; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  strong {{ color: #0f172a; }}
  code {{
    background: #f1f5f9;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9pt;
    font-family: 'SF Mono', 'Fira Code', monospace;
  }}

  /* ── Header ── */
  .header {{
    text-align: center;
    margin-bottom: 36px;
    padding: 32px 28px;
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 35%, #1e40af 65%, #7c3aed 100%);
    color: white;
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(15, 23, 42, 0.3);
  }}
  .header h1 {{
    color: white;
    border: none;
    margin: 0 0 6px 0;
    font-size: 24pt;
    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }}
  .header .subtitle {{
    font-size: 13pt;
    color: #e0e0f0;
    margin: 4px 0;
    font-weight: 300;
    letter-spacing: 0.5px;
  }}
  .header .meta {{
    font-size: 9pt;
    color: #a5b4fc;
    margin-top: 14px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
  }}

  /* ── Sentiment Charts Section ── */
  .charts-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin: 20px 0;
    justify-content: center;
  }}
  .chart-card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    text-align: center;
  }}
  .chart-card img {{
    max-width: 100%;
    height: auto;
  }}
  .chart-card .chart-title {{
    font-size: 9pt;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    font-weight: 600;
  }}
  .sentiment-kpi-row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin: 16px 0;
  }}
  .kpi-card {{
    flex: 1;
    text-align: center;
    padding: 16px 10px;
    background: linear-gradient(135deg, #f8fafc, #eff6ff);
    border-radius: 8px;
    border: 1px solid #e2e8f0;
  }}
  .kpi-card .kpi-value {{
    font-size: 22pt;
    font-weight: 800;
    color: #1e40af;
    line-height: 1;
  }}
  .kpi-card .kpi-label {{
    font-size: 8pt;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 6px;
  }}
  .kpi-card .kpi-sub {{
    font-size: 8.5pt;
    color: #94a3b8;
    margin-top: 2px;
  }}
  .drivers-list {{
    margin: 16px 0;
    padding: 0;
    list-style: none;
  }}
  .drivers-list li {{
    padding: 10px 14px;
    margin-bottom: 6px;
    background: #f8fafc;
    border-left: 3px solid #1e40af;
    border-radius: 0 6px 6px 0;
    font-size: 9.5pt;
    color: #334155;
  }}
  .drivers-list li::before {{
    content: "▸ ";
    color: #1e40af;
    font-weight: bold;
  }}

  /* ── Footer ── */
  .footer {{
    margin-top: 48px;
    padding: 20px 24px;
    border-top: 2px solid #e2e8f0;
    text-align: center;
    font-size: 8pt;
    color: #94a3b8;
    background: #f8fafc;
    border-radius: 0 0 8px 8px;
  }}
  .footer .brand {{
    font-weight: 700;
    color: #1e40af;
    font-size: 9pt;
    letter-spacing: 0.5px;
  }}

  /* ── Print optimization ── */
  h2 {{ page-break-before: auto; }}
  .charts-grid, .sentiment-kpi-row {{ page-break-inside: avoid; }}
  .chart-card {{ page-break-inside: avoid; }}
</style>
</head>
<body>
<div class="header">
  <h1>Industry News &amp; Sentiment Pulse</h1>
  <div class="subtitle">{industry} — Executive Intelligence Report</div>
  <div class="meta">{datetime.now().strftime('%B %d, %Y')} &middot; Powered by MARS AI Research Platform</div>
</div>
{body}
<div class="footer">
  <div class="brand">MARS AI Research Platform</div>
  Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
  &middot; All information sourced from publicly available data
  &middot; Verify independently before making business decisions
</div>
</body>
</html>"""


def _build_chart_html(sentiment_data: dict | None, chart_paths: dict | None) -> str:
    """Build the HTML fragment for the sentiment dashboard with charts."""
    if not sentiment_data:
        return ""

    overall = sentiment_data.get("overall_sentiment", {})
    momentum = sentiment_data.get("industry_momentum", {})
    risk = sentiment_data.get("risk_level", {})
    invest = sentiment_data.get("investment_activity", {})
    innov = sentiment_data.get("innovation_index", {})
    dist = sentiment_data.get("sentiment_distribution", {})
    confidence = sentiment_data.get("confidence_score", 65)
    drivers = sentiment_data.get("key_drivers", [])
    outlook = sentiment_data.get("outlook_signal", "Hold")

    trend_map = {"up": "↑", "down": "↓", "stable": "→"}
    trend_color = {"up": "#27ae60", "down": "#e74c3c", "stable": "#f39c12"}

    def _trend_html(t: str) -> str:
        arrow = trend_map.get(t, "→")
        color = trend_color.get(t, "#f39c12")
        return f'<span style="color:{color};font-weight:bold;font-size:14pt;">{arrow}</span>'

    # KPI row
    html = '<div class="sentiment-kpi-row">'
    kpis = [
        ("Overall", overall.get("label", "N/A"), overall.get("score", 50), overall.get("trend", "stable")),
        ("Momentum", momentum.get("label", "N/A"), momentum.get("score", 50), momentum.get("trend", "stable")),
        ("Risk", risk.get("label", "N/A"), risk.get("score", 50), risk.get("trend", "stable")),
        ("Investment", invest.get("label", "N/A"), invest.get("score", 50), invest.get("trend", "stable")),
        ("Innovation", innov.get("label", "N/A"), innov.get("score", 50), innov.get("trend", "stable")),
    ]
    for label, status, score, trend in kpis:
        html += f'''
        <div class="kpi-card">
          <div class="kpi-value">{score}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-sub">{status} {_trend_html(trend)}</div>
        </div>'''
    html += '</div>'

    # Charts grid
    if chart_paths:
        html += '<div class="charts-grid">'
        if "gauge" in chart_paths:
            html += f'''
            <div class="chart-card" style="flex:1;min-width:280px;">
              <div class="chart-title">Overall Sentiment Gauge</div>
              <img src="file://{chart_paths["gauge"]}" alt="Sentiment Gauge">
            </div>'''
        if "distribution" in chart_paths:
            html += f'''
            <div class="chart-card" style="flex:1;min-width:220px;">
              <div class="chart-title">Sentiment Distribution</div>
              <img src="file://{chart_paths["distribution"]}" alt="Sentiment Distribution">
            </div>'''
        html += '</div>'

        if "indicators" in chart_paths:
            html += f'''
            <div class="chart-card" style="margin:16px 0;">
              <div class="chart-title">Key Indicator Scores</div>
              <img src="file://{chart_paths["indicators"]}" alt="Indicator Scores" style="max-width:100%;">
            </div>'''

        if "outlook" in chart_paths:
            html += f'''
            <div style="text-align:center;margin:16px 0;">
              <img src="file://{chart_paths["outlook"]}" alt="Market Outlook" style="max-width:280px;">
            </div>'''

    # Key drivers list
    if drivers:
        html += '<h3>Key Sentiment Drivers</h3>'
        html += '<ul class="drivers-list">'
        for d in drivers[:5]:
            import html as html_mod
            html += f'<li>{html_mod.escape(str(d))}</li>'
        html += '</ul>'

    return html
