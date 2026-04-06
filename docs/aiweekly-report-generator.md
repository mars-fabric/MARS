# AI Weekly Report Generator — Complete Feature Guide

> **MARS Platform · Phase-Based AI Weekly News Report**
>
> A comprehensive guide covering the AI Weekly Report Generator: fundamentals, workflow stages, task lifecycle, AI techniques, and architecture.

---

## Table of Contents

1. [Basics — What Is the AI Weekly Report Generator?](#1-basics--what-is-the-ai-weekly-report-generator)
2. [All Stages in the Pipeline](#2-all-stages-in-the-pipeline)
3. [Task Flow — From `/tasks` to Final Report](#3-task-flow--from-tasks-to-final-report)
4. [Outcomes — Saved and Processed](#4-outcomes--saved-and-processed)
5. [AI Techniques Used](#5-ai-techniques-used)
6. [Architecture Deep Dive](#6-architecture-deep-dive)
7. [API Reference](#7-api-reference)
8. [Configuration & Model Defaults](#8-configuration--model-defaults)
9. [Error Handling & Troubleshooting](#9-error-handling--troubleshooting)
10. [Glossary](#10-glossary)

---

## 1. Basics — What Is the AI Weekly Report Generator?

### 1.1 Overview

The AI Weekly Report Generator is a **4-stage, human-in-the-loop AI pipeline** built into the MARS platform. It transforms a date range, topic, and source selection into a **professional, publication-ready AI weekly news digest** — from raw data collection through content curation to a polished final report — while keeping the human in control at every stage.

The feature is registered under the mode **`aiweekly`** and appears in the UI as **"AI Weekly Report"** on the Tasks page.

### 1.2 What It Produces

| Artifact | Format | Description |
|---|---|---|
| Raw Collection | Markdown | All items collected from RSS feeds, APIs, and web search |
| Curated Items | Markdown | Deduplicated, validated, and enriched master list |
| Draft Report | Markdown | 4-section report: Executive Summary, Key Highlights, Trends, Quick Reference |
| **Final Report** | Markdown | **Publication-ready report** polished for quality |

### 1.3 Key Design Principles

| Principle | Implementation |
|---|---|
| **Phase-Based Execution** | 4 discrete stages, each a `Phase` subclass |
| **Hybrid Architecture** | Stage 1 = direct Python tool calls (no LLM). Stages 2–4 = LLM with generate → specialist → review pipeline |
| **Human-in-the-loop** | Users review, edit, and refine output between every stage |
| **Token-safe** | Every LLM call uses `chunk_prompt_if_needed` with 0.75 safety margin |
| **Dynamic model** | Model resolved from `WorkflowConfig.default_llm_model`; user can override per-stage via UI model settings (centralized `useModelConfig` hook fetches available models from `/api/models/config`) |
| **Multi-agent** | Stages 2–3 use 3-agent pipeline (primary → specialist → reviewer). Stage 4 uses generate + review only (no specialist) |
| **Auto-completing** | `WorkflowRun.status` transitions to `"completed"` automatically when all 4 stages finish |
| **Real-time feedback** | REST polling delivers live console output during execution |
| **Resumable** | Tasks persist in SQLite/SQLAlchemy and can resume after reloads |

### 1.4 Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python, FastAPI, SQLAlchemy, asyncio |
| **Phase System** | `AIWeeklyPhaseBase` → 4 phase subclasses |
| **Data Collection** | `news_tools.py` — direct page scraping, RSS feeds, NewsAPI, GNews, web search |
| **Frontend** | React, TypeScript, Next.js |
| **Real-time** | REST polling (console output) |
| **Database** | SQLite via SQLAlchemy ORM |
| **Default LLM** | Dynamic from `WorkflowConfig.default_llm_model`; per-stage override via `config_overrides` (model, review_model, specialist_model) |

---

## 2. All Stages in the Pipeline

### Stage 1: Data Collection (Non-LLM)

**Class:** `AIWeeklyCollectionPhase` in `cmbagent/phases/aiweekly/collection_phase.py`

Runs all data collection tools directly in Python — no LLM involved. Calls:

| Step | Tool | Description |
|------|------|-------------|
| A | `announcements_noauth(limit=300)` | Broad official news page sweep |
| B | `scrape_official_news_pages(company=X)` × 22 | Direct HTML scraping + RSS feeds + web-search fallback per company (OpenAI, Google, DeepMind, Microsoft, Anthropic, Meta, Amazon, HuggingFace, NVIDIA, Intel, AMD, Apple, Boston Dynamics, Google Quantum, IBM, Quantinuum, Oracle, Samsung, Salesforce) |
| C | `curated_ai_sources_search(limit=40)` | 25+ curated AI news sources (NVIDIA Developer Blog, Google Cloud/Research, Microsoft Research/Azure, Oracle AI, Meta Engineering, etc.) |
| D | `newsapi_search()` | NewsAPI (if `NEWSAPI_KEY` set) |
| E | `gnews_search()` | Google News (if `GNEWS_API_KEY` set) |
| F | `multi_engine_web_search()` | DDG SDK → Bing → Yahoo → Brave fallback (targeted per under-covered company) |

**Deduplication:** By `(url, title[:80])` — first item wins.

**Output:** `raw_collection` — JSON + markdown summary of all collected items.

### Stage 2: Content Curation (LLM)

**Class:** `AIWeeklyCurationPhase` in `cmbagent/phases/aiweekly/curation_phase.py`

Takes raw collected items and produces a curated master list:
- Removes duplicates (same release under different titles)
- Validates dates within the coverage window
- Checks source credibility
- Ensures organization diversity
- Groups by organization

**Specialist:** Fact-checking specialist reviews for date accuracy, duplicates, and credibility.

**Output:** `curated_items` — validated master list with enriched descriptions.

### Stage 3: Report Generation (LLM)

**Class:** `AIWeeklyGenerationPhase` in `cmbagent/phases/aiweekly/generation_phase.py`

Writes the full 4-section report from curated items:

1. **Executive Summary** — 3–4 sentence overview
2. **Key Highlights & Developments** — all items with context and implications
3. **Trends & Strategic Implications** — cross-cutting patterns
4. **Quick Reference Table** — sortable table of organization, release, date, link

**Specialist:** Business analyst reviews for completeness, balance, and actionability.

**Output:** `draft_report` — complete markdown report.

### Stage 4: Quality Review (LLM)

**Class:** `AIWeeklyReviewPhase` in `cmbagent/phases/aiweekly/review_phase.py`

Final quality polish pass with style-dependent expansion:
- **Concise**: 2–4 sentences, ~50–80 words per item
- **Detailed**: ≥130 words with competitive context and business implications
- **Technical**: ≥130 words with metrics, architecture, technical depth

**No specialist** — just generate + review.

After the LLM pass, runs **programmatic verification** — 5 deterministic checks:
1. **URL verification** — calls `verify_reference_links(urls[:50])`, marks inaccessible URLs with `<!-- [LINK UNVERIFIED] -->`
2. **Date verification** — regex finds all `YYYY-MM-DD` dates, flags out-of-range with `<!-- [DATE OUT OF RANGE] -->`
3. **Placeholder detection** — checks for `example.com`, `[Insert`, `[TBD]`, `[URL]`, `[link]`, etc.
4. **Superlative detection** — flags `breakthrough`, `revolutionary`, `state-of-the-art`, `game-changing`, etc.
5. **Synthesis text removal** — regex removes `(Synthesis of ...)`, `(no single source...)`, `Source: N/A`, etc.

**Output:** `final_report` — publication-ready markdown.

---

## 3. Task Flow — From `/tasks` to Final Report

```
[User opens Tasks page]
    ↓
[Clicks "AI Weekly Report" → AIWeeklyReportTask.tsx]
    ↓
[Step 0: In-progress section (if any) + AIWeeklySetupPanel]
    │
    ├── If in-progress tasks exist:
    │     Cards shown ABOVE setup panel with resume/delete actions
    │     Click card → resumeTask(id) → jumps to latest step
    │
    └── Setup: selects date range, topics, sources, style, model settings
         ↓ POST /api/aiweekly/create + POST /{id}/stages/1/execute
[Step 1: Data Collection runs (console output polls via REST)]
    ↓ Auto-advances to Step 2 on completion
[Step 2: AIWeeklyReviewPanel — edit/preview curated items + refinement chat]
    ↓ Click "Next" → auto-executes Stage 3
[Step 3: AIWeeklyReviewPanel — edit/preview report draft + refinement chat]
    ↓ Click "Next" → auto-executes Stage 4
[Step 4: AIWeeklyReportPanel — final report preview + download artifacts]
```

### Key UI Components

| Wizard Step | Component | Purpose |
|---|---|---|
| 0 | `AIWeeklySetupPanel` | In-progress cards (above) + date range, topic chips, source chips, style selector, model settings (collapsible) |
| 1–3 | `AIWeeklyReviewPanel` | Split-view editor (60% edit/preview) + refinement chat (40%) |
| 4 | `AIWeeklyReportPanel` | Success banner, report preview, artifact downloads |

---

## 4. Outcomes — Saved and Processed

### Database (SQLAlchemy)

- **`WorkflowRun`** — one row per task, `mode="ai-weekly"`, `meta.task_config` stores user selections
- **`TaskStage`** — one row per stage (4 per task), `output_data.shared` stores content

### File System

Files are saved in `~/Desktop/cmbdir/weekly/{task_id[:8]}/input_files/`:

| File | Source |
|---|---|
| `task_config.json` | User selections from setup |
| `collection.md` | Stage 1 output |
| `curated.md` | Stage 2 output |
| `report_draft.md` | Stage 3 output |
| `report_final.md` | Stage 4 output |

---

## 5. AI Techniques Used

| Technique | Where |
|---|---|
| **Multi-source aggregation** | Stage 1 — RSS, APIs, web search across 35+ feeds (including NVIDIA, Google, Microsoft, Oracle, Meta official blogs) |
| **Generate → Specialist → Review pipeline** | Stages 2–3 — 3 LLM calls per stage |
| **Token chunking** | Every LLM call via `chunk_prompt_if_needed` (0.75 safety margin) |
| **Progressive context** | Each stage receives shared state from all prior stages |
| **Refinement chat** | Real-time LLM refinement on any editable stage |
| **Deduplication** | Two levels — Python exact-match (Stage 1) + LLM semantic dedup (Stage 2) |

---

## 6. Architecture Deep Dive

### Phase Class Hierarchy

```
Phase (base)
├── AIWeeklyCollectionPhase   (Stage 1 — no LLM, direct tool calls)
└── AIWeeklyPhaseBase         (Stages 2–4 — LLM with generate → specialist → review)
    ├── AIWeeklyCurationPhase
    ├── AIWeeklyGenerationPhase
    └── AIWeeklyReviewPhase
```

### Shared State Flow

```
Stage 1: raw_collection → Stage 2: curated_items → Stage 3: draft_report → Stage 4: final_report
```

Each stage receives all previously completed stage outputs via `_build_shared_state()`.

### Backend Router

`backend/routers/aiweekly.py` — 13 endpoints, prefix `/api/aiweekly`:

1. `POST /create` — creates task + 4 stage rows in DB
2. `POST /{id}/stages/{N}/execute` — launches async stage execution
3. `GET /recent` — list incomplete tasks for resume flow
4. `GET /{id}` — full task state with all stages
5. `GET /{id}/stages/{N}/content` — stage output markdown
6. `PUT /{id}/stages/{N}/content` — save user edits
7. `POST /{id}/stages/{N}/refine` — LLM refinement
8. `GET /{id}/stages/{N}/console` — streaming console lines
9. `POST /{id}/reset-from/{N}` — reset stages N+ to pending
10. `POST /{id}/stop` — cancel running stage, mark task as failed
11. `DELETE /{id}` — delete task + files
12. `GET /{id}/download/{filename}` — download artifact file
13. `GET /{id}/download-pdf/{filename}` — convert markdown to PDF and download

---

## 7. API Reference

### POST `/api/aiweekly/create`

Creates a new AI Weekly Report task.

**Request:**
```json
{
  "date_from": "2025-01-13",
  "date_to": "2025-01-19",
  "topics": ["llm", "cv"],
  "sources": ["github", "press-releases"],
  "style": "concise"
}
```

**Response:**
```json
{
  "task_id": "uuid",
  "work_dir": "/path/to/weekly/<id>",
  "stages": [
    {"stage_number": 1, "stage_name": "data_collection", "status": "pending"},
    {"stage_number": 2, "stage_name": "content_curation", "status": "pending"},
    {"stage_number": 3, "stage_name": "report_generation", "status": "pending"},
    {"stage_number": 4, "stage_name": "quality_review", "status": "pending"}
  ]
}
```

### POST `/api/aiweekly/{task_id}/stages/{stage_num}/execute`

Executes a stage asynchronously. Optional `config_overrides` for model and n_reviews.

### POST `/api/aiweekly/{task_id}/stages/{stage_num}/refine`

**Request:**
```json
{
  "message": "Add more detail about the OpenAI items",
  "content": "current markdown content..."
}
```

**Response:**
```json
{
  "refined_content": "improved markdown...",
  "message": "Content refined successfully"
}
```

### GET `/api/aiweekly/recent`

Lists incomplete AI Weekly tasks (status `executing` or `draft`) for the resume flow on the Tasks page. Returns up to 10 tasks ordered by `started_at` descending. Tasks at 100% progress (all stages completed) are filtered out — these should never appear because the backend now auto-transitions `WorkflowRun.status` to `"completed"` once all stages finish (see [Workflow Run Auto-Completion](#workflow-run-auto-completion)).

**Response:** Array of `AIWeeklyRecentTaskResponse` with `task_id`, `task`, `status`, `created_at`, `current_stage`, `progress_percent`.

### POST `/api/aiweekly/{task_id}/stop`

Stops a running AI Weekly task. Cancels any executing background `asyncio.Task`, marks running stages as `failed` with error `"Stopped by user"`, and sets the parent `WorkflowRun.status` to `"failed"`.

**Response:**
```json
{
  "status": "stopped",
  "task_id": "uuid",
  "cancelled_stages": ["uuid:1"]
}
```

---

## 8. Configuration & Model Defaults

| Setting | Default | Source |
|---|---|---|
| Model | `WorkflowConfig.default_llm_model` | Dynamic resolution; overridable per-stage from UI via `config_overrides.model` |
| Review model | Same as primary | Overridable via `config_overrides.review_model` |
| Specialist model | Same as primary | Overridable via `config_overrides.specialist_model` |
| Fallback model | `gpt-4o` | If WorkflowConfig unavailable |
| Temperature | `0.7` | `AIWeeklyPhaseConfig.temperature`; overridable via `config_overrides.temperature` |
| Max completion tokens | `16384` | `AIWeeklyPhaseConfig.max_completion_tokens` |
| Reviews per stage | `1` | `AIWeeklyPhaseConfig.n_reviews`; overridable via `config_overrides.n_reviews` |
| Multi-agent | `True` | `AIWeeklyPhaseConfig.multi_agent` |
| Stage timeout | `900s` | `_run_weekly_stage()` |
| Token safety margin | `0.75` | ``chunk_prompt_if_needed()`` |

### Model Selection — UI to Backend Flow

The model selection is fully end-to-end:

1. **UI:** `AIWeeklySetupPanel` renders a collapsible **"Model Settings"** section with 3 dropdowns (Primary, Review, Specialist). Model list is fetched from `/api/models/config` via the centralized `useModelConfig()` hook (falls back to a static list if the API is unavailable).
2. **Hook:** `useAIWeeklyTask.executeStage()` reads `stageConfig` and copies all non-empty fields (model, review_model, specialist_model, temperature, n_reviews) into `config_overrides`.
3. **API:** `POST /api/aiweekly/{id}/stages/{N}/execute` accepts `{ config_overrides }` in the request body.
4. **Backend:** `execute_aiweekly_stage()` extracts each override with fallback to defaults, then passes all 5 parameters to `_run_aiweekly_stage()`.
5. **Phase execution:** The phase is instantiated with `AIWeeklyPhaseConfig(model=..., review_model=..., specialist_model=..., temperature=..., n_reviews=...)`.

**Note:** Stage 1 (Data Collection) does not use an LLM — `config_overrides` are only applied for Stages 2–4.

---

## Workflow Run Auto-Completion

When the last stage in an AI Weekly task completes, the backend automatically transitions the parent `WorkflowRun.status` from `"executing"` to `"completed"` and sets `completed_at`. This happens in `_run_aiweekly_stage()` after each stage update — it queries all `TaskStage` rows for the task and checks if every stage has `status == "completed"`. If so, the `WorkflowRun` is finalized.

This ensures:
- Completed tasks no longer appear in `GET /api/aiweekly/recent` (which filters by `status in ["executing", "draft"]`)
- The "In Progress" section on the UI only shows genuinely in-progress tasks
- Database records accurately reflect true task lifecycle state

---

## 9. Error Handling & Troubleshooting

| Scenario | Behavior |
|---|---|
| Tool call fails in Stage 1 | Error logged, continues to next tool |
| Stage times out (900s) | Marked as `failed`, user can retry |
| LLM call fails | Phase returns error, stage marked failed |
| Token overflow | `chunk_prompt_if_needed` splits large prompts |
| No API keys for NewsAPI/GNews | Those steps skipped silently |

---

## 10. Glossary

| Term | Definition |
|---|---|
| **Stage** | One of the 4 pipeline phases (Collection, Curation, Generation, Review) |
| **Phase class** | Python class implementing a stage's logic |
| **Shared state** | Accumulated outputs from all completed stages |
| **Refinement chat** | Real-time LLM editing of stage content |
| **Token chunking** | Splitting oversized prompts into safe-length chunks |
| **Specialist** | Secondary LLM agent that reviews primary output |
