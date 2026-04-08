# AI Weekly Report Generator — End-to-End Integration Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Directory Structure](#3-directory-structure)
4. [The 4-Stage Pipeline](#4-the-4-stage-pipeline)
5. [Phase-Based Execution Engine](#5-phase-based-execution-engine)
6. [Shared State & Context Flow](#6-shared-state--context-flow)
7. [Backend API Reference](#7-backend-api-reference)
8. [Database Layer](#8-database-layer)
9. [Phase Classes & Prompts](#9-phase-classes--prompts)
10. [Frontend UI](#10-frontend-ui)
11. [Console Output & Real-Time Streaming](#11-console-output--real-time-streaming)
12. [Task Resumption](#12-task-resumption)
13. [Token Capacity Management](#13-token-capacity-management)
14. [Cost Tracking](#14-cost-tracking)
15. [End-to-End User Flow](#15-end-to-end-user-flow)
16. [Error Handling](#16-error-handling)
17. [Workflow Run Auto-Completion](#17-workflow-run-auto-completion)

---

## 1. Overview

The AI Weekly Report Generator is a **4-stage, human-in-the-loop AI pipeline** in MARS. It transforms a date range + topic/source selection into a publication-ready AI weekly report through interactive stages:

1. **Data Collection** → 2. **Content Curation** → 3. **Report Generation** → 4. **Quality Review**

Stage 1 uses **direct Python tool calls** (no LLM). Stages 2–4 use a **3-agent LLM pipeline** (Primary → Specialist → Reviewer) via `AIWeeklyPhaseBase`.

**Key technologies:**
- **Backend:** Python, FastAPI, SQLAlchemy, asyncio
- **Phase System:** `AIWeeklyPhaseBase` → 4 phase subclasses
- **Data Collection:** `news_tools.py` — direct page scraping, RSS feeds, NewsAPI, GNews, DDG/Bing/Yahoo/Brave; 26 curated sources covering AI/ML, hardware, robotics, quantum, and cloud/enterprise AI
- **Frontend:** React, TypeScript, Next.js
- **Real-time:** REST polling (console output)
- **Default LLM:** Dynamic from `WorkflowConfig.default_llm_model`; per-stage override via `config_overrides` (model, review_model, specialist_model, temperature, n_reviews)
- **Mode:** `"aiweekly"`

---

## 2. Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/Next.js)                       │
│                                                                       │
│  TaskList.tsx ──► AIWeeklyReportTask.tsx (5-step wizard)                │
│                    ├── AIWeeklySetupPanel.tsx       (Step 0)            │
│                    ├── AIWeeklyReviewPanel.tsx      (Steps 1–3)         │
│                    └── AIWeeklyReportPanel.tsx      (Step 4)            │
│                                                                       │
│  useAIWeeklyTask.ts ── state management, API calls, polling             │
└───────────┬───────────────────────────────────────────────────────────┘
            │ REST API
            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                              │
│                                                                       │
│  routers/aiweekly.py ── REST endpoints + phase execution engine       │
│    _run_aiweekly_stage():                                            │
│      1. _load_phase_class(stage_num) ── importlib dynamic load        │
│      2. PhaseClass(config=...)                                         │
│      3. PhaseContext(task, work_dir, shared_state)                     │
│      4. await phase.execute(ctx)                                       │
│      5. Extract output, track cost, update DB                          │
│      6. On all-complete → _generate_cost_summary() → cost_summary.md │
│                                                                       │
│  _ConsoleCapture ── thread-safe stdout/stderr → REST console buffer   │
└───────────┬──────────────────────────────┬────────────────────────────┘
            │                              │
            ▼                              ▼
┌────────────────────────┐    ┌─────────────────────────────────────────┐
│   SQLite (SQLAlchemy)  │    │       cmbagent/phases/aiweekly/           │
│                        │    │                                         │
│  WorkflowRun (task)    │    │  collection_phase.py  (Stage 1, no LLM)│
│  TaskStage   (×4)      │    │  curation_phase.py    (Stage 2, LLM)   │
│  CostRecord            │    │  generation_phase.py  (Stage 3, LLM)   │
│  output_data.shared    │    │  review_phase.py      (Stage 4, LLM)   │
└────────────────────────┘    │  base.py              (shared base)     │
                              │                                         │
                              │  Uses: news_tools.py (Stage 1)          │
                              │  Uses: rfp/token_utils.py (all stages)  │
                              └─────────────────────────────────────────┘
```

---

## 3. Directory Structure

```
cmbagent/phases/aiweekly/
  __init__.py              # Package exports
  base.py                  # AIWeeklyPhaseBase, AIWeeklyPhaseConfig, WeeklyTaskConfig
  collection_phase.py      # Stage 1: Direct tool calls (no LLM)
  curation_phase.py        # Stage 2: LLM content curation
  generation_phase.py      # Stage 3: LLM report writing
  review_phase.py          # Stage 4: LLM quality review

backend/
  models/aiweekly_schemas.py # Pydantic request/response models
  routers/aiweekly.py        # 13 REST endpoints

mars-ui/
  types/aiweekly.ts        # TypeScript interfaces + wizard constants
  hooks/useAIWeeklyTask.ts   # React hook — state, API calls, polling
  components/weekly/
    AIWeeklySetupPanel.tsx   # Date range, topics, sources, style
    AIWeeklyReviewPanel.tsx  # Edit/preview + refinement chat
    AIWeeklyReportPanel.tsx  # Final report + download artifacts
  components/tasks/
    AIWeeklyReportTask.tsx   # Main orchestrator (5-step wizard + stepper)

cmbagent/external_tools/
  news_tools.py            # Direct page scraping, RSS feeds, NewsAPI, GNews, web search
```

---

## 4. The 4-Stage Pipeline

| # | Stage | Class | Type | Specialist | Output Key |
|---|---|---|---|---|---|
| 1 | Data Collection | `AIWeeklyCollectionPhase` | Direct Python (no LLM) | N/A | `raw_collection` |
| 2 | Content Curation | `AIWeeklyCurationPhase` | LLM (3-agent) | Fact-checker | `curated_items` |
| 3 | Report Generation | `AIWeeklyGenerationPhase` | LLM (3-agent) | Business analyst | `draft_report` |
| 4 | Quality Review | `AIWeeklyReviewPhase` | LLM (generate+review) | None | `final_report` |

### Stage 1: Data Collection (Non-LLM)

Calls each tool sequentially, deduplicates by `(url, title[:80])`:

1. `announcements_noauth(limit=300)` — broad official news page sweep
2. `scrape_official_news_pages(company=X)` × 19 companies — direct HTML scraping + RSS + web-search fallback (OpenAI, Google, DeepMind, Microsoft, Anthropic, Meta, Amazon, HuggingFace, NVIDIA, Intel, AMD, Apple, Boston Dynamics, Google Quantum, IBM, Quantinuum, Oracle, Samsung, Salesforce)
3. `curated_ai_sources_search(limit=40)` — 26 curated AI news sources (NVIDIA Developer Blog, Google Cloud/Research, Microsoft Research/Azure, Oracle AI, Meta Engineering, etc.)
4. `newsapi_search()` — NewsAPI (if key available)
5. `gnews_search()` — Google News (if key available)
6. `multi_engine_web_search()` — DDG SDK → Bing → Yahoo → Brave fallback (targeted per under-covered company)

### Stages 2–4: LLM Pipeline

Each stage follows the `AIWeeklyPhaseBase.execute()` pattern:

```
1. Build user prompt (from shared state)
2. chunk_prompt_if_needed(user_prompt, system_prompt, model)  ← token safety
3. Generate primary output via safe_completion()
4. [If specialist] Run specialist review → merge improvements
5. Run reviewer pass → final polished output
6. Save to shared_state[output_key] and to file
```

---

## 5. Phase-Based Execution Engine

### `_run_aiweekly_stage()` in `backend/routers/aiweekly.py`

```python
async def _run_aiweekly_stage(task_id, stage_num, task_text, work_dir, task_config, model, n_reviews):
    # 1. Capture stdout/stderr for console streaming
    cap = _ConsoleCapture(buf_key, sys.stdout)
    sys.stdout = cap

    # 2. Load phase class via importlib
    PhaseClass = _load_phase_class(stage_num)

    # 3. Build shared state from prior completed stages
    shared_state = _build_shared_state(task_id, stage_num, task_config)

    # 4. Create phase context
    ctx = PhaseContext(workflow_id=task_id, task=task_text, work_dir=work_dir, shared_state=shared_state)

    # 5. Execute with 900s timeout
    result = await asyncio.wait_for(phase.execute(ctx), timeout=900)

    # 6. Update DB with output + status
```

### Phase Class Loading

```python
_PHASE_CLASSES = {
    1: "cmbagent.phases.aiweekly.collection_phase:AIWeeklyCollectionPhase",
    2: "cmbagent.phases.aiweekly.curation_phase:AIWeeklyCurationPhase",
    3: "cmbagent.phases.aiweekly.generation_phase:AIWeeklyGenerationPhase",
    4: "cmbagent.phases.aiweekly.review_phase:AIWeeklyReviewPhase",
}
```

Dynamic loading via `importlib.import_module()` — same pattern as RFP.

---

## 6. Shared State & Context Flow

```
Stage 1 output:
  shared_state["raw_collection"] = "markdown of all collected items"

Stage 2 receives:
  shared_state = {task_config, raw_collection}
  Output: shared_state["curated_items"]

Stage 3 receives:
  shared_state = {task_config, raw_collection, curated_items}
  Output: shared_state["draft_report"]

Stage 4 receives:
  shared_state = {task_config, raw_collection, curated_items, draft_report}
  Output: shared_state["final_report"]
```

Built by `_build_shared_state()` which queries all completed `TaskStage` rows for the task.

---

## 7. Backend API Reference

All endpoints prefixed with `/api/aiweekly`.

| Method | Path | Description |
|---|---|---|
| POST | `/create` | Create task + 4 stage DB rows |
| POST | `/{id}/stages/{N}/execute` | Launch async stage execution |
| GET | `/{id}` | Full task state (all stages) |
| GET | `/{id}/stages/{N}/content` | Stage output markdown |
| PUT | `/{id}/stages/{N}/content` | Save user edits |
| POST | `/{id}/stages/{N}/refine` | LLM refinement of content |
| GET | `/{id}/stages/{N}/console` | Console output lines (polling) |
| POST | `/{id}/reset-from/{N}` | Reset stages N+ to pending |
| GET | `/recent` | List incomplete tasks for resume flow |
| POST | `/{id}/stop` | Cancel running stage, mark task as failed |
| DELETE | `/{id}` | Delete task + work_dir |
| GET | `/{id}/download/{filename}` | Download artifact file |
| GET | `/{id}/download-pdf/{filename}` | Convert markdown to PDF and download |

### Console Polling

Frontend polls `GET /{id}/stages/{N}/console?since={index}` every 2 seconds. Returns new lines since the given index. Uses thread-safe `_ConsoleCapture` that intercepts `sys.stdout` during execution.

### Refinement

`POST /{id}/stages/{N}/refine` calls `safe_completion()` with the current content + user instruction. Token budget is computed to avoid overflow.

---

## 8. Database Layer

### WorkflowRun

| Column | Value |
|---|---|
| `mode` | `"aiweekly"` |
| `agent` | `"phase_orchestrator"` |
| `status` | `"executing"` → `"completed"` (auto-set when all 4 stages complete) / `"failed"` |
| `meta.work_dir` | `~/Desktop/cmbdir/aiweekly/<id[:8]>` |
| `meta.task_config` | `{date_from, date_to, topics, sources, style}` |
| `meta.orchestration` | `"phase-based"` |

### TaskStage (4 per task)

| Column | Description |
|---|---|
| `parent_run_id` | → WorkflowRun.id |
| `stage_number` | 1–4 |
| `stage_name` | `data_collection`, `content_curation`, `report_generation`, `quality_review` |
| `status` | `pending` → `running` → `completed` / `failed` |
| `output_data` | `{"shared": {"<key>": "markdown content"}}` |
| `error_message` | Error text if failed |

---

## 9. Phase Classes & Prompts

### AIWeeklyPhaseBase (`base.py`)

Shared base for Stages 2–4. Provides:
- `execute()` — generate → specialist → review pipeline
- Token chunking via `rfp/token_utils.chunk_prompt_if_needed()`
- Dynamic model resolution from `WorkflowConfig`
- `get_style_rule()` — per-style word-count minimums

### Stage 2: AIWeeklyCurationPhase

**System prompt:** Senior AI news editor — curate, validate, deduplicate.

**Specialist:** Fact-checking specialist — date accuracy, credibility, diversity.

**User prompt builds from:** `raw_collection` + `task_config` (date range, topics).

### Stage 3: AIWeeklyGenerationPhase

**System prompt:** Senior analyst writing enterprise-grade weekly report.

**Specialist:** Business analyst — completeness, balance, actionability.

**User prompt builds from:** `curated_items` + style/topic config.

**Report structure:** Executive Summary → Key Highlights → Trends → Quick Reference Table.

### Stage 4: AIWeeklyReviewPhase

**System prompt:** Quality editor — final polish for publication readiness.

**No specialist.** Uses generate + review only.

After the LLM pass, runs **programmatic verification** — 5 deterministic checks:
1. **URL verification** — `verify_reference_links(urls[:50])`, marks inaccessible URLs with `<!-- [LINK UNVERIFIED] -->`
2. **Date verification** — regex finds all `YYYY-MM-DD` dates, flags out-of-range with `<!-- [DATE OUT OF RANGE] -->`
3. **Placeholder detection** — checks for `example.com`, `[Insert`, `[TBD]`, `[URL]`, `[link]`, etc.
4. **Superlative detection** — flags `breakthrough`, `revolutionary`, `state-of-the-art`, `game-changing`, etc.
5. **Synthesis text removal** — regex removes `(Synthesis of ...)`, `(no single source...)`, `Source: N/A`, etc.

---

## 10. Frontend UI

### Component Hierarchy

```
TaskList.tsx (card: "AI Weekly Report")
  └─ AIWeeklyReportTask.tsx (wizard orchestrator)
       ├─ Header + Stepper (5 steps: Setup, Collection, Curation, Generation, Review)
       ├─ Step 0 panel:
       │    ├─ In-progress section (fetches GET /api/aiweekly/recent)
       │    │    └─ Resume cards with progress bar, delete button
       │    └─ AIWeeklySetupPanel.tsx
       │         ├─ Date range, topics, sources, style
       │         └─ Model Settings (collapsible, uses useModelConfig())
       │              ├─ Primary Model dropdown
       │              ├─ Review Model dropdown
       │              └─ Specialist Model dropdown
       ├─ AIWeeklyReviewPanel.tsx (Steps 1–3)
       │    ├─ ResizableSplitPane: Edit/Preview (left) + RefinementChat (right)
       │    │    Both panes resizable down to 200px minimum
       │    └─ ExecutionProgress (while running)
       └─ AIWeeklyReportPanel.tsx (Step 4)
            ├─ Success banner
            ├─ Report preview (MarkdownRenderer)
            └─ Artifact download links
```

**In-progress section:** When on Step 0, `AIWeeklyReportTask.tsx` fetches `GET /api/aiweekly/recent` on mount. If there are in-progress tasks, they are rendered as clickable cards **above** the setup panel (inside the same page — not a separate landing page). Each card shows the task name, current stage, progress bar, and resume/delete actions. The currently active task (if any) is filtered out of the list. When more than ~5 tasks are listed, the section becomes scrollable (max-height 320px with overflow-y auto) to prevent the setup panel from being pushed too far down.

**Model settings:** The setup panel includes a collapsible "Model Settings" section that uses the centralized `useModelConfig()` hook to fetch available models from `/api/models/config` (with static fallback). Users can select different models for the Primary (generation), Review (quality check), and Specialist (fact-check) roles.

### Hook: `useAIWeeklyTask.ts`

Manages all state and API interactions:

| Method | Purpose |
|---|---|
| `createTask()` | POST /create |
| `executeStage()` | POST /{id}/stages/{N}/execute |
| `fetchStageContent()` | GET /{id}/stages/{N}/content |
| `saveStageContent()` | PUT /{id}/stages/{N}/content |
| `refineContent()` | POST /{id}/stages/{N}/refine |
| `loadTaskState()` | GET /{id} |
| `resumeTask()` | GET /{id} + jump to latest step |
| `resetFromStage()` | POST /{id}/reset-from/{N} |
| `deleteTask()` | DELETE /{id} |

### Type Definitions (`weekly.ts`)

Key interfaces: `AIWeeklyStage`, `AIWeeklyTaskState`, `AIWeeklyCreateResponse`, `AIWeeklyRefineResponse`, `AIWeeklyRefinementMessage`.

Constants: `AIWEEKLY_STEP_LABELS`, `AIWEEKLY_WIZARD_STEP_TO_STAGE`, `AIWEEKLY_STAGE_SHARED_KEYS`.

**Note:** `wsRef` is vestigial — all real-time communication uses REST polling, not WebSockets.

---

## 11. Console Output & Real-Time Streaming

During execution, `_ConsoleCapture` intercepts all `print()` / `sys.stdout` output from the phase class and buffers it in memory. Frontend polls `GET /console?since=N` every 2 seconds and appends new lines to `consoleOutput[]`.

Stage status is tracked via `GET /{id}` polling every 5 seconds.

---

## 12. Task Resumption

### Resume Flow — In Progress Section

When `AIWeeklyReportTask.tsx` loads, it fetches incomplete AI Weekly tasks via `GET /api/aiweekly/recent` (regardless of whether there's an active task). On Step 0, if any in-progress tasks exist, they appear as **"In Progress" cards rendered above the setup panel** with:

- Blue newspaper icon
- Task name (e.g., "AI Weekly Report — 2026-03-30 to 2026-04-06")
- Current stage name + progress percentage
- Progress bar
- **Resume arrow** — click to call `resumeTask(id)` which loads the task at the right step
- **Delete (X) button** — calls `DELETE /api/aiweekly/{id}` after confirm dialog

The currently active task is filtered out of the in-progress list to avoid duplication. When more than ~5 tasks are listed, the section becomes scrollable (max-height 320px) to keep the page layout manageable. When no task is active, the user sees the in-progress cards above the normal setup form — both are always visible (not a separate landing page).

### Resume Logic

`resumeTask(id)` in `useAIWeeklyTask.ts` loads task state via `GET /{id}`, finds the latest completed stage, and sets `currentStep` to the next wizard step. If a stage is currently `running`, the hook reconnects console polling. Users can:
- Review and edit completed stages
- Re-run failed stages (Retry button)
- Reset later stages and re-execute from any point

### Stop / Cancel

`POST /api/aiweekly/{id}/stop` cancels any running `asyncio.Task` background stages for the task and marks them as `failed` with error `"Stopped by user"`. The parent `WorkflowRun.status` is set to `"failed"`.

---

## 13. Token Capacity Management

Every LLM call in Stages 2–4 uses `chunk_prompt_if_needed()` from `cmbagent.phases.rfp.token_utils`:

1. Count tokens in system prompt + user prompt
2. If total > `model_context × 0.75`, split user prompt into chunks
3. Process each chunk separately, accumulate results
4. Dynamic `max_completion_tokens` = `context_limit - prompt_tokens - safety_buffer`

Refinement endpoint also computes token budget before calling `safe_completion()`.

---

## 14. Cost Tracking

Each LLM call's token usage is tracked per-stage and recorded to the database via `CostRepository`.

### Per-Stage Cost Storage

- Stages 2–4 return token counts in `output_data["cost"]` (`prompt_tokens`, `completion_tokens`, `total_tokens`)
- The router calculates `cost_usd = (prompt_tokens × 0.002 + completion_tokens × 0.008) / 1000` and stores it in both:
  - `CostRecord` (database table) for persistent tracking
  - `output_data["cost"]["cost_usd"]` per TaskStage for the cost summary
- Stage 1 (Data Collection) has no LLM cost — tokens will be 0

### Cost Summary File

When all 4 stages complete, the backend generates `cost_summary.md` in `input_files/` with:

- **Per-stage breakdown table** — stage name, model, prompt/completion/total tokens, cost (USD)
- **Totals row** — aggregated across all stages
- **Summary section** — bullet-point totals

Downloadable from the **Generated Artifacts** section on Step 4 via `GET /api/aiweekly/{id}/download/cost_summary.md`.

### Total Cost in API Response

`GET /api/aiweekly/{id}` returns `total_cost: { prompt_tokens, completion_tokens, total_tokens }` aggregated from all completed stages.

---

## 15. End-to-End User Flow

1. User opens Tasks → clicks "AI Weekly Report"
2. **Setup:** Configures date range, picks topics/sources, selects style
3. **Create + Execute Stage 1:** `POST /create` → `POST /stages/1/execute`
4. **Data Collection runs:** Console shows progress ("RSS/openai: 12 items", etc.)
5. **Stage 1 completes:** Wizard advances to Step 1, shows collected data
6. User reviews raw collection, optionally edits, clicks **Next**
7. **Stage 2 auto-executes:** Curation runs (LLM + specialist)
8. User reviews curated list, uses refinement chat, clicks **Next**
9. **Stage 3 auto-executes:** Report generation (LLM + specialist)
10. User reviews draft report, refines via chat, clicks **Next**
11. **Stage 4 auto-executes:** Quality review (LLM only)
12. **Final report displayed** with download links for all artifacts + cost summary

---

## 16. Error Handling

| Error | Handling |
|---|---|
| Tool call failure (Stage 1) | Logged + skipped, continues to next tool |
| Stage timeout (900s) | `asyncio.TimeoutError` → stage marked `failed` |
| LLM API error | Caught, stage marked `failed` with error message |
| Token overflow | `chunk_prompt_if_needed` auto-splits |
| Missing API keys | Stage 1 skips NewsAPI/GNews steps silently |
| Invalid filename in download | HTTP 400 (path traversal protection) |
| Task not found | HTTP 404 |

---

## 17. Workflow Run Auto-Completion

When the last stage completes, `_run_aiweekly_stage()` automatically checks whether all `TaskStage` rows for the task have `status == "completed"`. If so, it transitions the parent `WorkflowRun`:

- `status` → `"completed"`
- `completed_at` → current UTC timestamp

This ensures:
- Fully finished tasks no longer appear in `GET /api/aiweekly/recent` (which filters `status in ["executing", "draft"]`)
- The "In Progress" section accurately reflects only genuinely active tasks
- Database audit trail records the precise completion time
