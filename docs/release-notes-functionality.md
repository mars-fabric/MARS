# Release Notes — Complete Functionality Specification

> Auto-generated specification covering every function, endpoint, type, prompt, and data flow in the Release Notes pipeline.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Stage Definitions & Data Model](#2-stage-definitions--data-model)
3. [Backend — API Endpoints](#3-backend--api-endpoints)
4. [Backend — Internal Functions](#4-backend--internal-functions)
5. [Pydantic Schemas (Request/Response Models)](#5-pydantic-schemas-requestresponse-models)
6. [Frontend — TypeScript Types](#6-frontend--typescript-types)
7. [Frontend — React Hook (`useReleaseNotesTask`)](#7-frontend--react-hook-usereleasenotesstask)
8. [Frontend — React Components (`ReleaseNotesTask.tsx`)](#8-frontend--react-components-releasenoteststsx)
9. [Helper Functions (`releasenotes_helpers.py`)](#9-helper-functions-releasenotes_helperspy)
10. [One-Shot Helper Functions (`releasenotes_oneshot_helpers.py`)](#10-one-shot-helper-functions-releasenotes_oneshot_helperspy)
11. [Prompt Templates](#11-prompt-templates)
12. [Data Flow & Context Carryover](#12-data-flow--context-carryover)
13. [Console Streaming](#13-console-streaming)
14. [AI Refinement Flow](#14-ai-refinement-flow)
15. [PDF Export](#15-pdf-export)
16. [Error Handling & Recovery](#16-error-handling--recovery)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                             │
│                                                                 │
│  ReleaseNotesTask.tsx ──► useReleaseNotesTask.ts hook           │
│       │                         │                               │
│       │ UI Panels:              │ API calls via apiFetch():     │
│       │  SetupPanel             │  POST /api/release-notes/create
│       │  ExecutionStagePanel    │  POST .../stages/{n}/execute  │
│       │  AnalysisStagePanel     │  GET  .../stages/{n}/content  │
│       │  ReviewStagePanel       │  PUT  .../stages/{n}/content  │
│       │  MigrationPanel         │  POST .../stages/{n}/refine   │
│       │  InlineRefinementChat   │  GET  .../stages/{n}/console  │
│       │                         │  GET  .../{task_id}           │
│       │                         │  GET  .../recent              │
│       │                         │  POST .../{task_id}/resume    │
│       │                         │  POST .../{task_id}/stop      │
│       │                         │  DELETE .../{task_id}         │
└───────┼─────────────────────────┼───────────────────────────────┘
        │                         │
        │  Next.js Rewrite Proxy  │  /api/:path* → http://localhost:8201/api/:path*
        │  (proxyTimeout: 300s)   │
        │                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI, port 8201)                                   │
│                                                                 │
│  router = APIRouter(prefix="/api/release-notes")                │
│                                                                 │
│  releasenotes.py (1655 lines)                                   │
│    ├── Endpoints (11 routes)                                    │
│    ├── Background execution (_run_stage, _run_planning_control) │
│    ├── Git operations (_run_collect_and_diff)                   │
│    ├── AI stages (_run_analysis/release_notes/migration)        │
│    ├── Console capture (_ConsoleCapture)                        │
│    └── PDF export (WeasyPrint + markdown)                       │
│                                                                 │
│  Database: SQLAlchemy + SQLite                                  │
│    ├── WorkflowRun   (parent task record)                       │
│    └── TaskStage     (per-stage records, output_data JSON)      │
│                                                                 │
│  AI Engine: cmbagent.one_shot()                                 │
│    ├── Prompts: cmbagent/task_framework/prompts/releasenotes/   │
│    ├── Helpers: releasenotes_helpers.py                         │
│    └── Helpers: releasenotes_oneshot_helpers.py                 │
└─────────────────────────────────────────────────────────────────┘
```

**Tech Stack:**
- **Frontend:** Next.js 16.2.1, React, TypeScript, Tailwind CSS
- **Backend:** FastAPI (Python), port 8201
- **Database:** SQLAlchemy + SQLite (WorkflowRun + TaskStage models)
- **AI Engine:** cmbagent framework → `one_shot()` → OpenAI GPT-4.1 / GPT-4o
- **PDF Export:** WeasyPrint + Python `markdown` library
- **Proxy:** Next.js rewrite proxy with 300s timeout (`experimental.proxyTimeout`)

---

## 2. Stage Definitions & Data Model

### 2.1 Stage Definitions (`STAGE_DEFS`)

```python
STAGE_DEFS = [
    {
        "number": 1,
        "name": "collect_and_diff",
        "shared_key": "diff_context",
        "file": "diff_context.md"
    },
    {
        "number": 2,
        "name": "analysis",
        "shared_key": "analysis_comparison",
        "file": "analysis_comparison.md",
        "multi_doc": True,
        "doc_keys": ["analysis_base", "analysis_head", "analysis_comparison"],
        "doc_files": ["analysis_base.md", "analysis_head.md", "analysis_comparison.md"]
    },
    {
        "number": 3,
        "name": "release_notes",
        "shared_key": "release_notes",
        "file": "release_notes.md",
        "multi_doc": True,
        "doc_keys": ["release_notes_commercial", "release_notes_developer", "release_notes_code"],
        "doc_files": ["release_notes_commercial.md", "release_notes_developer.md", "release_notes_code.py"]
    },
    {
        "number": 4,
        "name": "migration",
        "shared_key": "migration_script",
        "file": "migration_script.md"
    },
    {
        "number": 5,
        "name": "package",
        "shared_key": None,
        "file": None
    },
]
```

### 2.2 File Categories (`FILE_CATEGORIES`)

Used by `_categorise_file()` to classify changed files:

| Category    | Extensions/Patterns                                                              |
|-------------|----------------------------------------------------------------------------------|
| `code`      | `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.java`, `.go`, `.rs`, `.c`, `.cpp`, etc.   |
| `config`    | `.json`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`, `.env`, `.properties`         |
| `database`  | `.sql`, `.migration`, `.prisma`                                                  |
| `migration` | `.alembic`, `.migrate`                                                           |
| `docs`      | `.md`, `.rst`, `.txt`, `.adoc`                                                   |
| `infra`     | `Dockerfile`, `docker-compose`, `.tf`, `.hcl`, `Makefile`, `Jenkinsfile`, `.github` |
| `test`      | `test_`, `_test.`, `.spec.`, `.test.`                                            |

### 2.3 Global State

```python
_running_tasks: Dict[str, asyncio.Task] = {}      # Key: "{task_id}:{stage_num}"
_console_buffers: Dict[str, List[str]] = {}        # Key: "{task_id}:{stage_num}"
_console_lock = threading.Lock()                   # Thread-safe console access
_db_initialized = False                            # Lazy DB init flag
```

### 2.4 Database Models

**WorkflowRun** (parent task record):
| Column           | Type     | Description                                      |
|------------------|----------|--------------------------------------------------|
| `id`             | UUID str | Task ID (primary key)                            |
| `session_id`     | str      | Session ID from session manager                  |
| `mode`           | str      | Always `"release-notes"`                         |
| `agent`          | str      | `"engineer"`                                     |
| `model`          | str      | `"gpt-4o"`                                       |
| `status`         | str      | `executing` / `completed` / `failed`             |
| `task_description` | str   | Human-readable task summary                      |
| `started_at`     | datetime | UTC timestamp                                    |
| `completed_at`   | datetime | UTC timestamp (set on completion)                |
| `meta`           | JSON     | Contains `work_dir`, `repo_url`, `repo_name`, `base_branch`, `head_branch`, `auth_token`, `extra_instructions`, `config`, `session_id` |

**TaskStage** (per-stage record):
| Column          | Type     | Description                                       |
|-----------------|----------|---------------------------------------------------|
| `id`            | UUID     | Stage ID (primary key)                            |
| `parent_run_id` | str      | FK → WorkflowRun.id                              |
| `stage_number`  | int      | 1–5                                               |
| `stage_name`    | str      | `collect_and_diff` / `analysis` / etc.            |
| `status`        | str      | `pending` / `running` / `completed` / `failed`    |
| `input_data`    | JSON     | `{repo_url, repo_name, base_branch, head_branch}` |
| `output_data`   | JSON     | Contains `shared` dict and `artifacts` dict       |
| `output_files`  | list     | File paths of generated artifacts                 |
| `started_at`    | datetime | UTC timestamp                                     |
| `completed_at`  | datetime | UTC timestamp                                     |
| `error_message` | str      | Error text on failure                             |

---

## 3. Backend — API Endpoints

### 3.1 `POST /api/release-notes/create`

**Purpose:** Create a new Release Notes task with 5 pending stages.

**Request Body:** `ReleaseNotesCreateRequest`
```json
{
  "repo_url": "https://github.com/owner/repo",
  "base_branch": "release/v1.0",
  "head_branch": "release/v2.0",
  "auth_token": "ghp_...",           // optional
  "extra_instructions": "Focus on...", // optional
  "config": {},                       // optional
  "work_dir": null                    // optional override
}
```

**Response:** `ReleaseNotesCreateResponse`
```json
{
  "task_id": "uuid",
  "session_id": "uuid",
  "work_dir": "/path/to/sessions/.../tasks/uuid",
  "stages": [
    { "stage_number": 1, "stage_name": "collect_and_diff", "status": "pending", ... },
    ...
  ]
}
```

**Logic:**
1. Validate repo URL (must be HTTPS GitHub/GitLab)
2. Validate branches (both required, must differ)
3. Generate task UUID
4. Create session via `get_session_manager().create_session()`
5. Create work directory and `input_files/` subdirectory
6. Insert `WorkflowRun` record with `status="executing"`
7. Insert 5 `TaskStage` records with `status="pending"`
8. Return task_id, session_id, work_dir, and stage list

---

### 3.2 `POST /api/release-notes/{task_id}/stages/{stage_num}/execute`

**Purpose:** Trigger asynchronous stage execution.

**Request Body:** `ReleaseNotesExecuteRequest` (optional)
```json
{ "config_overrides": {} }
```

**Response:**
```json
{ "status": "executing", "stage_num": 1, "task_id": "uuid" }
```

**Logic:**
1. Validate `stage_num` (1–5)
2. Check no duplicate execution (409 if already running)
3. Verify all prior stages are completed (400 if not)
4. Build `shared_state` via `build_shared_state()` (context carryover)
5. Mark stage as `"running"` in DB
6. Launch `asyncio.create_task(_run_stage(...))` in background
7. Store task reference in `_running_tasks["{task_id}:{stage_num}"]`
8. Return immediately

---

### 3.3 `GET /api/release-notes/{task_id}`

**Purpose:** Get full task state for UI rendering and resume.

**Response:** `ReleaseNotesTaskStateResponse`
```json
{
  "task_id": "uuid",
  "session_id": "uuid",
  "repo_url": "...",
  "repo_name": "repo",
  "base_branch": "...",
  "head_branch": "...",
  "status": "executing",
  "work_dir": "...",
  "created_at": "...",
  "stages": [...],
  "current_stage": 2,
  "progress_percent": 40.0,
  "total_cost_usd": 0.05
}
```

**Logic:**
1. Load `WorkflowRun` from DB
2. Load all `TaskStage` records
3. Calculate progress via `repo.get_task_progress()`
4. Get total cost from `CostRepository`
5. Determine `current_stage` (first running, then first non-completed)

---

### 3.4 `GET /api/release-notes/recent`

**Purpose:** List recent Release Notes tasks for the task list / resume UI.

**Response:** `List[ReleaseNotesRecentTaskResponse]`

**Logic:**
1. Query `WorkflowRun` where `mode="release-notes"`, ordered by `started_at DESC`, limit 20
2. For each run, calculate progress and current_stage

---

### 3.5 `POST /api/release-notes/{task_id}/resume`

**Purpose:** Resume a task by auto-executing the next pending/failed stage.

**Response:** `ReleaseNotesResumeResponse`

**Logic:**
1. Find first non-completed stage (pending or failed)
2. If a stage is "running" but `_running_tasks` shows done → treat as retryable
3. Validate all prior stages are completed
4. Build shared_state, mark stage running, launch background task
5. Return `{status: "executing", stage_num: N}`

---

### 3.6 `GET /api/release-notes/{task_id}/stages/{stage_num}/content`

**Purpose:** Retrieve stage output content and shared_state for the editor.

**Response:** `ReleaseNotesStageContentResponse`
```json
{
  "stage_number": 2,
  "stage_name": "analysis",
  "status": "completed",
  "content": "# Analysis...",
  "shared_state": { "analysis_base": "...", ... },
  "output_files": ["analysis_base.md", ...],
  "documents": {
    "analysis_base": "...",
    "analysis_head": "...",
    "analysis_comparison": "..."
  }
}
```

**Logic:**
1. Load stage from DB
2. If `output_data` exists:
   - For `multi_doc` stages: populate `documents` dict from `shared` keys
   - For single-doc stages: get content from `shared[shared_key]`
3. Fallback: read from file on disk (`input_files/{file}`)

---

### 3.7 `PUT /api/release-notes/{task_id}/stages/{stage_num}/content`

**Purpose:** Save user edits to stage content.

**Request Body:** `ReleaseNotesContentUpdateRequest`
```json
{
  "content": "# Updated content...",
  "field": "analysis_base"
}
```

**Logic:**
1. Verify stage is `completed` or `failed` (400 otherwise)
2. Update `output_data.shared[field]` in DB
3. Write content to the appropriate file on disk:
   - Multi-doc stages: map `field` → `doc_files` via `doc_keys`
   - Single-doc stages: write to `sdef["file"]`

---

### 3.8 `POST /api/release-notes/{task_id}/stages/{stage_num}/refine`

**Purpose:** AI-powered content refinement using GPT-4o.

**Request Body:** `ReleaseNotesRefineRequest`
```json
{
  "message": "Make it more concise",
  "content": "# Current content..."
}
```

**Response:** `ReleaseNotesRefineResponse`
```json
{
  "refined_content": "# Refined content...",
  "message": "Content refined successfully"
}
```

**Logic:**
1. Build prompt:
   ```
   You are helping a software engineer refine release documentation.
   Below is the current content, followed by the user's edit request.
   --- CURRENT CONTENT ---
   {request.content}
   --- USER REQUEST ---
   {request.message}
   Provide the refined version. Return ONLY the refined content, no explanations.
   ```
2. Call `safe_completion()` with `model="gpt-4o"`, `temperature=0.7`, `max_tokens=4096`
3. Execute via `loop.run_in_executor(ThreadPoolExecutor)` (non-blocking)
4. Return `refined or request.content` (fallback if LLM returns empty)

---

### 3.9 `GET /api/release-notes/{task_id}/stages/{stage_num}/console`

**Purpose:** Poll console output for running stages.

**Query Params:** `since` (int, default 0) — index to fetch from

**Response:**
```json
{ "lines": ["Starting collect_and_diff...", ...], "next_index": 5, "is_done": false }
```

---

### 3.10 `GET /api/release-notes/{task_id}/stages/{stage_num}/download`

**Purpose:** Download a stage output file as markdown.

**Query Params:** `doc_key` (optional, for multi-doc stages like analysis)

**Logic:**
1. Resolve filename from `STAGE_DEFS` (multi-doc: `doc_key` → `doc_files`)
2. Return `FileResponse` with `media_type="text/markdown"`

---

### 3.11 `GET /api/release-notes/{task_id}/stages/{stage_num}/download-pdf`

**Purpose:** Download stage output as PDF.

**Query Params:** `doc_key` (optional)

**Logic:**
1. Resolve markdown content from DB `shared_state` or file on disk
2. Convert markdown → HTML via `markdown.markdown()` (extensions: tables, fenced_code, codehilite, toc, sane_lists)
3. Wrap in HTML with `_PDF_CSS` stylesheet (A4, 2cm margins, professional typography)
4. Convert HTML → PDF via `weasyprint.HTML(string=full_html).write_pdf()`
5. Save PDF to `input_files/` and return `FileResponse`

---

### 3.12 `POST /api/release-notes/{task_id}/stop`

**Purpose:** Cancel a running task.

**Logic:**
1. Cancel all `asyncio.Task` objects in `_running_tasks` for this task_id
2. Mark all "running" stages as "failed" with error "Stopped by user"
3. Set parent `WorkflowRun.status = "failed"`

---

### 3.13 `DELETE /api/release-notes/{task_id}`

**Purpose:** Delete a task and all its data.

**Logic:**
1. Cancel running background tasks
2. Clean up console buffers
3. Delete all `TaskStage` rows
4. Delete `WorkflowRun` row
5. Remove work directory from disk (`shutil.rmtree`)

---

## 4. Backend — Internal Functions

### 4.1 Database Helpers

| Function | Signature | Description |
|----------|-----------|-------------|
| `_get_db()` | `→ Session` | Initialize DB (lazy) and return a SQLAlchemy session |
| `_get_stage_repo(db, session_id)` | `→ TaskStageRepository` | Get stage repository for CRUD operations |
| `_get_cost_repo(db, session_id)` | `→ CostRepository` | Get cost repository for LLM cost tracking |
| `_get_work_dir(task_id, session_id, base_work_dir)` | `→ str` | Compute work directory path: `{base}/sessions/{session_id}/tasks/{task_id}` |
| `_get_session_id_for_task(task_id, db)` | `→ str` | Look up session_id from WorkflowRun table |
| `build_shared_state(task_id, up_to_stage, db, session_id)` | `→ Dict` | Reconstruct shared_state from all completed stages up to `up_to_stage`. Merges `output_data["shared"]` from each. |
| `_stage_to_response(stage)` | `→ ReleaseNotesStageResponse` | Convert DB stage object to Pydantic response model |

### 4.2 Console Capture

**`_ConsoleCapture` class:**
- Wraps `sys.stdout` / `sys.stderr`
- Writes to both the original stream AND `_console_buffers[buf_key]`
- Thread-safe via `_console_lock`
- Methods: `write(text)`, `flush()`, `fileno()`, `isatty()`

**`_get_console_lines(buf_key, since_index)`:**
- Returns lines from `_console_buffers[buf_key]` starting at `since_index`

### 4.3 Git Helpers

| Function | Signature | Description |
|----------|-----------|-------------|
| `_validate_repo_url(url)` | `→ str` | Validate HTTPS GitHub/GitLab URL, strip `.git` suffix |
| `_categorise_file(filepath)` | `→ str` | Classify file by extension into categories (code, config, database, etc.) |
| `_run_git(args, cwd, timeout)` | `→ CompletedProcess` | Execute git command with subprocess, 120s default timeout |

### 4.4 Background Stage Execution

#### `_run_stage(task_id, stage_num, work_dir, shared_state, config_overrides, session_id)`

**Purpose:** Main background execution dispatcher.

**Logic:**
1. Initialize console buffer
2. Dispatch to stage-specific function:
   - Stage 1 → `_run_collect_and_diff()`
   - Stages 2–4 → `_run_planning_control_stage()`
   - Stage 5 → `_run_package()`
3. On success: persist `output_data` to DB, mark stage "completed"
4. Check if all stages done → mark `WorkflowRun.status = "completed"`
5. On error: log, mark stage "failed", mark workflow "failed"
6. Cleanup: remove from `_running_tasks`

#### `_run_planning_control_stage(task_id, stage_num, sdef, buf_key, work_dir, shared_state, config_overrides, session_id)`

**Purpose:** Run AI stages (2–4) with full callback infrastructure.

**7-Phase Pattern (mirrors Deepresearch):**
1. **Setup DB session** for cost + event tracking
2. **Build callbacks** — `WorkflowCallbacks` with:
   - `on_agent_msg`: Log agent messages to `EventRepository`
   - `on_code_exec`: Log code execution events
   - `on_tool`: Log tool call events
   - `on_cost_update`: Collect costs via `CostCollector`
   - Merge with `create_print_callbacks()` for stdout logging
3. **Dispatch** to stage-specific one-shot function
4. *(Phase 4/5 — execution happens inside dispatched function)*
5. **Cost safety net** — scan `work_dir` for cost files via `cost_collector.collect_from_work_dir()`
6. **Close** callback DB session

#### `_run_one_shot_sync(task, agent, work_dir, config_overrides, callbacks)`

**Purpose:** Synchronous wrapper around `cmbagent.one_shot()` for use with `asyncio.to_thread()`.

**Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| `task` | required | Prompt string |
| `agent` | `"researcher"` | Agent name |
| `work_dir` | `tempfile.gettempdir()` | Working directory |
| `config_overrides` | `{}` | Model overrides |
| `callbacks` | `None` | WorkflowCallbacks |

**Key settings:**
- `researcher_model`: from overrides or `"gpt-4.1"`
- `engineer_model`: from overrides or `"gpt-4o"`
- `max_rounds`: from overrides or `15`
- `clear_work_dir=False`

#### `_run_analysis_one_shot(task_id, buf_key, work_dir, shared_state, config_overrides, helpers, callbacks)`

**Purpose:** Stage 2 — Run 3 sequential one-shot calls for analysis documents.

**Documents produced:**
1. `analysis_base` → `analysis_base.md` (Base Branch Summary)
2. `analysis_head` → `analysis_head.md` (Head Branch Summary)
3. `analysis_comparison` → `analysis_comparison.md` (Detailed Comparison)

**Logic:**
1. Format prompts with `{repo_name, base_branch, head_branch, diff_context}`
2. For each document:
   - Create subdirectory `stage_2_{doc_key}`
   - Run `_run_one_shot_sync()` via `asyncio.to_thread()`
   - Extract result via `helpers.extract_stage_result()`
   - Save to file via `helpers.save_stage_file()`
   - Log progress to console buffer
3. Unified stdout/stderr capture (redirected to `_ConsoleCapture`)
4. Return via `helpers.build_analysis_output()`

#### `_run_release_notes_one_shot(task_id, buf_key, work_dir, shared_state, config_overrides, helpers, callbacks)`

**Purpose:** Stage 3 — Single one-shot call for release notes (commercial + developer).

**Logic:**
1. Truncate `diff_context` to 20K chars (strip full diff, keep stat/file list)
2. Format prompt with all analysis documents + diff context + extra instructions
3. Run `_run_one_shot_sync()` via `asyncio.to_thread()`
4. Extract result, save to `release_notes.md`
5. Return via `helpers.build_release_notes_output()`

#### `_run_migration_one_shot(task_id, buf_key, work_dir, shared_state, config_overrides, helpers, callbacks)`

**Purpose:** Stage 4 — Single one-shot call for migration scripts.

**Logic:**
1. Truncate `diff_context` to 15K chars
2. Format prompt with analysis, release notes, migration type
3. Run `_run_one_shot_sync()` via `asyncio.to_thread()`
4. Extract result, save to `migration_script.md`
5. Return via `helpers.build_migration_output()`

#### `_run_collect_and_diff(shared_state, work_dir, buf_key)`

**Purpose:** Stage 1 — Clone repo, capture SHAs, generate diffs.

**Logic:**
1. Clone repo (shallow, `--depth=100`) to temp directory
2. Fetch base branch
3. Get SHAs for both branches via `git rev-parse`
4. Generate `git log --oneline` (commits + merges)
5. Generate `git diff --name-status` (changed files)
6. Categorize each file via `_categorise_file()`
7. Generate `git diff --stat` and full `git diff`
8. Truncate full diff to 200K chars if needed
9. Build `diff_context` markdown document with:
   - Header (branch comparison, commit/file counts)
   - Diff stat
   - Changed files (grouped by category, max 50 per category)
   - Full diff
10. Save to `input_files/diff_context.md`
11. Return `output_data` with `shared` dict containing all data

#### `_run_package(task_id, shared_state, buf_key)`

**Purpose:** Stage 5 — Bundle summary of all outputs.

**Logic:**
1. Assemble package metadata:
   - task_id, repo_name, branches, counts
   - Boolean flags: has_analysis, has_release_notes, has_code_guide, has_migration_script
2. Return `{"shared": {}, "package": {...}}`

---

## 5. Pydantic Schemas (Request/Response Models)

**File:** `backend/models/releasenotes_schemas.py`

### Request Models

| Model | Endpoint | Fields |
|-------|----------|--------|
| `ReleaseNotesCreateRequest` | `POST /create` | `repo_url` (str, required), `base_branch` (str, required), `head_branch` (str, required), `auth_token` (optional), `extra_instructions` (optional), `config` (optional dict), `work_dir` (optional) |
| `ReleaseNotesExecuteRequest` | `POST .../execute` | `config_overrides` (optional dict) |
| `ReleaseNotesContentUpdateRequest` | `PUT .../content` | `content` (str, required), `field` (str, required) |
| `ReleaseNotesRefineRequest` | `POST .../refine` | `message` (str, required), `content` (str, required) |
| `ReleaseNotesMigrationRequest` | `POST .../stages/4/execute` | `migration_type` (str, default "database"), `extra_instructions` (optional) |

### Response Models

| Model | Fields |
|-------|--------|
| `ReleaseNotesStageResponse` | `stage_number`, `stage_name`, `status`, `started_at`, `completed_at`, `error` |
| `ReleaseNotesCreateResponse` | `task_id`, `session_id`, `work_dir`, `stages[]` |
| `ReleaseNotesStageContentResponse` | `stage_number`, `stage_name`, `status`, `content`, `shared_state`, `output_files`, `documents` |
| `ReleaseNotesRefineResponse` | `refined_content`, `message` |
| `ReleaseNotesTaskStateResponse` | `task_id`, `session_id`, `repo_url`, `repo_name`, `base_branch`, `head_branch`, `status`, `work_dir`, `created_at`, `stages[]`, `current_stage`, `progress_percent`, `total_cost_usd` |
| `ReleaseNotesRecentTaskResponse` | `task_id`, `repo_name`, `base_branch`, `head_branch`, `status`, `created_at`, `current_stage`, `progress_percent` |
| `ReleaseNotesResumeResponse` | `task_id`, `status`, `stage_num`, `message` |

---

## 6. Frontend — TypeScript Types

**File:** `mars-ui/types/releasenotes.ts`

### Types & Interfaces

| Type | Description |
|------|-------------|
| `ReleaseNotesStageStatus` | `'pending' \| 'running' \| 'completed' \| 'failed'` |
| `ReleaseNotesStage` | Stage info: `stage_number`, `stage_name`, `status`, `started_at`, `completed_at`, `error` |
| `ReleaseNotesTaskState` | Full task: `task_id`, `repo_url`, `repo_name`, branches, `status`, `stages[]`, `current_stage`, `progress_percent` |
| `ReleaseNotesStageContent` | Stage output: `content`, `shared_state`, `output_files`, `documents` |
| `ReleaseNotesCreateResponse` | `task_id`, `work_dir`, `stages[]` |
| `ReleaseNotesRefineResponse` | `refined_content`, `message` |
| `RefinementMessage` | Chat message: `id`, `role` (user/assistant), `content`, `timestamp` |
| `ReleaseNotesWizardStep` | `0 \| 1 \| 2 \| 3 \| 4 \| 5` |
| `AnalysisDocKey` | `'analysis_base' \| 'analysis_head' \| 'analysis_comparison'` |

### Constants

```typescript
RELEASE_NOTES_STEP_LABELS = ['Setup', 'Clone & Diff', 'AI Analysis', 'Release Notes', 'Migration', 'Package']

WIZARD_STEP_TO_STAGE = { 0: null, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5 }

STAGE_SHARED_KEYS = { 1: 'diff_context', 2: 'analysis_comparison', 3: 'release_notes', 4: 'migration_script' }

ANALYSIS_DOC_KEYS = [
  { key: 'analysis_base', label: 'Last Release Branch', file: 'analysis_base.md' },
  { key: 'analysis_head', label: 'Current Release Branch', file: 'analysis_head.md' },
  { key: 'analysis_comparison', label: 'Detailed Comparison', file: 'analysis_comparison.md' },
]
```

---

## 7. Frontend — React Hook (`useReleaseNotesTask`)

**File:** `mars-ui/hooks/useReleaseNotesTask.ts`

### State Variables

| State | Type | Description |
|-------|------|-------------|
| `taskId` | `string \| null` | Current task UUID |
| `taskState` | `ReleaseNotesTaskState \| null` | Full task state from backend |
| `currentStep` | `ReleaseNotesWizardStep` | Active wizard step (0–5) |
| `isLoading` | `boolean` | Loading indicator |
| `error` | `string \| null` | Error message |
| `editableContent` | `string` | Current editor content |
| `refinementMessages` | `RefinementMessage[]` | Chat history for AI refinement |
| `consoleOutput` | `string[]` | Console lines from backend |
| `isExecuting` | `boolean` | Stage is running |
| `stageDocuments` | `Record<string, string> \| null` | Multi-doc content (for analysis stage) |

### Refs

| Ref | Purpose |
|-----|---------|
| `pollRef` | Task state polling interval (5s) |
| `consolePollRef` | Console output polling interval (2s) |
| `consoleIndexRef` | Console line cursor for incremental fetching |
| `taskIdRef` | Stable task ID reference for callbacks |

### Functions

#### `apiFetch(path, options) → Promise<any>`
Wrapper around `apiFetchWithRetry()`. Throws on non-OK response with `body.detail` as error message.

#### `loadTaskState(id) → Promise<ReleaseNotesTaskState>`
Calls `GET /api/release-notes/{id}`, updates `taskState`.

#### `createTask(repoUrl, baseBranch, headBranch, authToken?, extraInstructions?) → Promise<string | null>`
1. `POST /api/release-notes/create`
2. Set taskId, load task state
3. Return task_id or null on error

#### `startPolling(id, stageNum)`
Start 5-second interval polling `loadTaskState()`. Stops when stage is completed or failed.

#### `startConsolePoll(id, stageNum)`
Start 2-second interval polling `GET .../stages/{stageNum}/console?since={index}`. Appends new lines to `consoleOutput`.

#### `executeStage(stageNum, configOverrides?)`
1. `POST /api/release-notes/{id}/stages/{stageNum}/execute`
2. Start both polling intervals
3. Set `isExecuting = true`

#### `fetchStageContent(stageNum) → Promise<ReleaseNotesStageContent | null>`
1. `GET /api/release-notes/{id}/stages/{stageNum}/content`
2. Sanitize content (strip `"None"` / `"null"` strings)
3. Update `editableContent` and `stageDocuments`

#### `saveStageContent(stageNum, content, field)`
`PUT /api/release-notes/{id}/stages/{stageNum}/content` with `{content, field}`.

#### `refineContent(stageNum, message, content) → Promise<string | null>`
1. Add user message to `refinementMessages`
2. `POST /api/release-notes/{id}/stages/{stageNum}/refine`
3. Add assistant message to `refinementMessages`
4. Return refined content

#### `resumeTask(id)`
1. Set taskId, load task state
2. Determine resume step:
   - If stage is "running" → `resumeStep = stage_number`, start polling
   - If stage is "completed" → `resumeStep = stage_number + 1`
   - Otherwise → `resumeStep = stage_number`
3. Set `currentStep`

#### `clearError()`
Set `error = null`.

---

## 8. Frontend — React Components (`ReleaseNotesTask.tsx`)

**File:** `mars-ui/components/tasks/ReleaseNotesTask.tsx` (1221 lines)

### 8.1 `ReleaseNotesTask` (Main Component)

**Props:**
- `onBack: () => void` — Navigate back to task list
- `resumeTaskId?: string | null` — Auto-resume existing task

**State:**
- Form fields: `repoUrl`, `baseBranch`, `headBranch`, `authToken`, `extraInstructions`
- `isFormValid`: computed — URL starts with `https://`, both branches non-empty, branches differ

**Renders:**
- Header with back button and title
- Error banner (dismissible)
- Stepper (horizontal, 6 steps)
- Conditional panel based on `currentStep` (0–5)

**Stepper logic:** Maps `RELEASE_NOTES_STEP_LABELS` to stepper steps with status derived from `taskState.stages`.

---

### 8.2 `SetupPanel`

**Purpose:** Step 0 — Repository configuration form.

**Fields:**
- Repository URL (text input)
- Base Branch (text input)
- Head Branch (text input)
- Auth Token (password input, optional)
- Additional Instructions (textarea, optional)
- Branch visual (base → head diagram)
- "Create Task & Continue" button

---

### 8.3 `ExecutionStagePanel`

**Purpose:** Steps 1 (Clone & Diff) and 5 (Package) — auto-execute and show console.

**Props:** `stageNum`, `stageName`, `description`, `onNext`, `onBack`

**Renders:**
- Pre-execution: description + "Run" button
- During execution: `ExecutionProgress` component with console output
- Post-execution: Back/Next/Retry buttons

---

### 8.4 `AnalysisStagePanel`

**Purpose:** Step 2 — 3-tab document editor with AI refinement.

**State:**
- `activeTab`: `AnalysisDocKey` (`analysis_base` / `analysis_head` / `analysis_comparison`)
- `mode`: `'edit'` / `'preview'`
- `isSaving`, `saveIndicator`, `contentLoaded`

**Layout:**
- Toolbar: title, save indicator, Download All, Preview/Edit, Save
- 3 tabs (Last Release Branch / Current Release Branch / Detailed Comparison)
- Left: Editor (textarea) or Preview (MarkdownRenderer)
- Right sidebar (320px): download button + `InlineRefinementChat`
- Navigation: Back / Next buttons

**Key callbacks:**
- `handleSave()`: Save current tab content to backend + update `stageDocuments`
- `handleRefine(message)`: Call `refineContent(2, message, editableContent)`
- `handleApplyRefinement(content)`: Guard against empty, update editor + `stageDocuments`
- `handleDownload(docKey)`: Open download URL in new tab
- `handleDownloadAll()`: Download all 3 documents

---

### 8.5 `ReviewStagePanel`

**Purpose:** Step 3 — Release Notes editor with AI refinement.

**Props:** `stageNum`, `stageName`, `sharedKey`, `onNext`, `onBack`

**Layout:**
- Toolbar: title, save indicator, PDF download, Preview/Edit, Save
- Left: Editor or Preview
- Right sidebar (320px): AI Refinement chat
- Navigation: Back / Next

**Key callbacks:**
- `handleSave()`: Save to backend via `saveStageContent(stageNum, editableContent, sharedKey)`
- `handleRefine(message)`: Call `refineContent(stageNum, message, editableContent)`
- `handleApplyRefinement(content)`: Guard `if (content && content.trim())`, then `setEditableContent(content)`

---

### 8.6 `MigrationPanel`

**Purpose:** Step 4 — Auto-execute migration, then show editor with refinement.

**State:** `autoTriggered`, `contentLoaded`, `mode`, `isSaving`, `saveIndicator`

**Key behavior:**
- **Auto-execution:** On mount, if stage is pending, auto-trigger `executeStage(4, { migration_type: 'full' })`
- After completion: show editor with PDF download + AI refinement sidebar

**Key callbacks:**
- `handleSave()`: Save to backend with `field='migration_script'`
- `handleRefine(message)`: Refine via `refineContent(4, message, editableContent)`
- `handleApplyRefinement(content)`: Guard against empty, update editor
- Retry: Reset `autoTriggered` to re-trigger execution

---

### 8.7 `InlineRefinementChat`

**Purpose:** Reusable lightweight chat component for AI refinement.

**Props:**
- `messages: RefinementMessage[]` — Chat history
- `onSend: (message: string) => Promise<string | null>` — Send refinement request
- `onApply: (content: string) => void` — Apply refined content to editor

**Renders:**
- Scrollable message list (max 320px height)
- Each message: colored bubble (user = accent, assistant = overlay)
- Assistant messages: "Apply" button to apply content to editor
- Message preview: truncated to 300 chars
- Input bar: text input + send button (Enter to send)
- Loading state: spinner on send button

---

## 9. Helper Functions (`releasenotes_helpers.py`)

**File:** `cmbagent/task_framework/releasenotes_helpers.py`

### Default Model Configurations

```python
ANALYSIS_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

RELEASE_NOTES_DEFAULTS = { ... }  # Same structure
MIGRATION_DEFAULTS = { ... }      # Same structure
```

### Kwargs Builders (for `planning_and_control_context_carryover`)

| Function | Stage | Description |
|----------|-------|-------------|
| `build_analysis_base_kwargs(...)` | 2a | Build kwargs for base branch analysis P&C call |
| `build_analysis_head_kwargs(...)` | 2b | Build kwargs for head branch analysis P&C call |
| `build_analysis_comparison_kwargs(...)` | 2c | Build kwargs for comparison report P&C call |
| `build_release_notes_kwargs(...)` | 3 | Build kwargs for release notes P&C call |
| `build_migration_kwargs(...)` | 4 | Build kwargs for migration script P&C call |

Each builder:
1. Imports the relevant planner + researcher prompts
2. Merges defaults with `config_overrides`
3. Creates subdirectory via `create_work_dir()`
4. Formats prompts with context variables
5. Returns dict with all `planning_and_control_context_carryover()` parameters

### Output Builders

| Function | Returns |
|----------|---------|
| `build_analysis_output(base, head, comparison, artifacts, chat_histories)` | `{"shared": {analysis_base, analysis_head, analysis_comparison}, "artifacts": {...}, "documents": [...]}` |
| `build_release_notes_output(text, file_path, chat_history)` | `{"shared": {release_notes: text}, "artifacts": {...}, "chat_history": [...]}` |
| `build_migration_output(text, type, file_path, chat_history)` | `{"shared": {migration_script: text, migration_type: type}, "artifacts": {...}, "chat_history": [...]}` |

### Utility Functions

#### `extract_stage_result(results: dict) → str`

1. Try extracting from `"researcher"` agent in chat_history
2. Try `"researcher_response_formatter"` agent
3. Fallback: scan ALL messages, pick longest non-empty content
4. Validate via `_is_meaningful()` — rejects `None`, `null`, `TERMINATE`, empty strings
5. Clean via `extract_clean_markdown()` from shared utilities
6. Raise `ValueError` if no content found

#### `save_stage_file(content, work_dir, filename) → str`

Write content to `{work_dir}/input_files/{filename}` and return path.

#### `_is_meaningful(text: str | None) → bool`

Returns `False` for: `None`, empty, `"None"`, `"null"`, `"TERMINATE"`, `"NONE"`, `"NULL"`, `"none"`.

---

## 10. One-Shot Helper Functions (`releasenotes_oneshot_helpers.py`)

**File:** `cmbagent/task_framework/releasenotes_oneshot_helpers.py`

### Default Configuration

```python
ONESHOT_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "default_llm_model": "gpt-4.1",
    "default_formatter_model": "o3-mini",
}
```

### Kwargs Builders (for `cmbagent.one_shot()`)

| Function | Stage | Description |
|----------|-------|-------------|
| `build_analysis_base_oneshot_kwargs(...)` | 2a | One-shot kwargs for base branch analysis |
| `build_analysis_head_oneshot_kwargs(...)` | 2b | One-shot kwargs for head branch analysis |
| `build_analysis_comparison_oneshot_kwargs(...)` | 2c | One-shot kwargs for comparison analysis |
| `build_release_notes_oneshot_kwargs(...)` | 3 | One-shot kwargs for release notes |
| `build_migration_oneshot_kwargs(...)` | 4 | One-shot kwargs for migration scripts |

Each builder:
1. Imports the relevant one-shot prompt from `prompts/releasenotes/oneshot.py`
2. Merges `ONESHOT_DEFAULTS` with `config_overrides`
3. Creates subdirectory via `create_work_dir()`
4. Formats prompt with context variables
5. Returns dict: `{task, agent="researcher", max_rounds=15, max_n_attempts=2, ...}`

**Re-exports from `releasenotes_helpers`:** `extract_stage_result`, `save_stage_file`, `build_analysis_output`, `build_release_notes_output`, `build_migration_output`

---

## 11. Prompt Templates

**Directory:** `cmbagent/task_framework/prompts/releasenotes/`

### 11.1 Analysis Prompts (`analysis.py`) — 6 prompts

| Prompt | Type | Used By | Template Variables |
|--------|------|---------|-------------------|
| `base_planner_prompt` | Planner | P&C stage 2a | `{repo_name, base_branch, head_branch}` |
| `base_researcher_prompt` | Researcher | P&C + one-shot stage 2a | `{repo_name, base_branch, head_branch, diff_context}` |
| `head_planner_prompt` | Planner | P&C stage 2b | `{repo_name, base_branch, head_branch}` |
| `head_researcher_prompt` | Researcher | P&C + one-shot stage 2b | `{repo_name, base_branch, head_branch, diff_context}` |
| `comparison_planner_prompt` | Planner | P&C stage 2c | `{repo_name, base_branch, head_branch}` |
| `comparison_researcher_prompt` | Researcher | P&C + one-shot stage 2c | `{repo_name, base_branch, head_branch, diff_context}` |

**Output sections per document:**
- **Base:** Release Overview, Features, Architecture, API Surface, Configuration, Database Schema, Infrastructure, Known Limitations
- **Head:** Release Overview, New Features, Architecture (updated), API Surface, Configuration, Database Schema, Infrastructure, Bug Fixes, Known Limitations
- **Comparison:** Executive Summary, New Features, Modified Features, Removed/Deprecated, Breaking Changes, API Changes, Database Changes, Config Changes, Infrastructure Changes, Performance Impact, Security Changes, Migration Guide, Risk Assessment

### 11.2 Release Notes Prompts (`release_notes.py`) — 2 prompts

| Prompt | Template Variables |
|--------|-------------------|
| `release_notes_planner_prompt` | `{repo_name, base_branch, head_branch}` |
| `release_notes_researcher_prompt` | `{repo_name, base_branch, head_branch, diff_context, analysis_base, analysis_head, analysis_comparison, extra_instructions_section}` |

**Produces 2 documents:**
1. **Commercial Release Notes** — What's New, Improvements, Bug Fixes, Known Issues, Getting Started
2. **Developer Release Notes** — Overview, New Features, Bug Fixes, Breaking Changes, Migration Notes, Impact Analysis, Infrastructure Changes, API Reference Changes

### 11.3 Migration Prompts (`migration.py`) — 2 prompts

| Prompt | Template Variables |
|--------|-------------------|
| `migration_planner_prompt` | `{repo_name, base_branch, head_branch, migration_type}` |
| `migration_researcher_prompt` | `{repo_name, base_branch, head_branch, migration_type, diff_context, analysis_comparison, release_notes, extra_instructions_section}` |

**Covers 4 migration types:**
- **Database:** CREATE/ALTER TABLE, data migrations, rollback, validation, verification
- **API:** Endpoint changes, schema changes, backward compatibility, versioning
- **Infrastructure:** New services, config changes, deployment steps, rollback
- **Comprehensive:** All of the above

### 11.4 One-Shot Prompts (`oneshot.py`) — 5 prompts

| Prompt | Stage | Template Variables |
|--------|-------|-------------------|
| `oneshot_analysis_base_task` | 2a | `{repo_name, base_branch, head_branch, diff_context}` |
| `oneshot_analysis_head_task` | 2b | `{repo_name, base_branch, head_branch, diff_context}` |
| `oneshot_analysis_comparison_task` | 2c | `{repo_name, base_branch, head_branch, diff_context}` |
| `oneshot_release_notes_task` | 3 | `{repo_name, base_branch, head_branch, diff_context, analysis_base, analysis_head, analysis_comparison, extra_instructions_section}` |
| `oneshot_migration_task` | 4 | `{repo_name, base_branch, head_branch, diff_context, analysis_comparison, release_notes, migration_type, extra_instructions_section}` |

---

## 12. Data Flow & Context Carryover

### Stage Progression with `shared_state`

```
Stage 1: collect_and_diff
  Output → shared: { diff_context, repo_name, base_branch, head_branch,
                      commit_count, file_count, categorised, diff_stat,
                      base_sha, head_sha, commits, merges, categorised_files,
                      full_diff }
                ↓
          build_shared_state(up_to_stage=2) merges all completed stages
                ↓
Stage 2: analysis
  Input  ← shared_state: { diff_context, repo_name, base_branch, head_branch, ... }
  Output → shared: { analysis_base, analysis_head, analysis_comparison }
                ↓
          build_shared_state(up_to_stage=3)
                ↓
Stage 3: release_notes
  Input  ← shared_state: { diff_context, analysis_base, analysis_head,
                            analysis_comparison, extra_instructions, ... }
  Output → shared: { release_notes }
                ↓
          build_shared_state(up_to_stage=4)
                ↓
Stage 4: migration
  Input  ← shared_state: { diff_context, analysis_comparison, release_notes,
                            extra_instructions, ... }
  Output → shared: { migration_script, migration_type }
                ↓
          build_shared_state(up_to_stage=5)
                ↓
Stage 5: package
  Input  ← shared_state: all accumulated data
  Output → package summary (metadata only, no new shared state)
```

### `build_shared_state()` function
```python
def build_shared_state(task_id, up_to_stage, db, session_id):
    """Reconstruct shared_state from completed stages — context carryover."""
    stages = repo.list_stages(parent_run_id=task_id)
    shared = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared
```

Before dispatching a stage, `execute_stage()` also adds:
```python
shared_state["repo_url"] = meta.get("repo_url", "")
shared_state["repo_name"] = meta.get("repo_name", "")
shared_state["base_branch"] = meta.get("base_branch", "")
shared_state["head_branch"] = meta.get("head_branch", "")
shared_state["auth_token"] = meta.get("auth_token")
shared_state["extra_instructions"] = meta.get("extra_instructions", "")
```

---

## 13. Console Streaming

### Backend

**Capture mechanism:**
- Each stage gets a `buf_key = "{task_id}:{stage_num}"`
- Before execution, `_ConsoleCapture` replaces `sys.stdout/sys.stderr`
- Writes go to both the original stream AND `_console_buffers[buf_key]`
- Thread-safe via `_console_lock`

**API endpoint:**
```
GET /api/release-notes/{task_id}/stages/{stage_num}/console?since=0
→ { "lines": [...], "next_index": N, "is_done": bool }
```

### Frontend

**Polling mechanism:**
- `startConsolePoll(id, stageNum)` — 2-second interval
- Fetches `?since={consoleIndexRef.current}`
- Appends new lines to `consoleOutput` state
- `consoleIndexRef.current` tracks cursor position

**Display:** `ExecutionProgress` component renders console lines as a scrollable terminal-like view.

---

## 14. AI Refinement Flow

### Sequence

```
1. User types instruction in InlineRefinementChat input
2. InlineRefinementChat.handleSend() called
3. Parent's handleRefine(message) called
4. hook.refineContent(stageNum, message, editableContent) called
5. User message added to refinementMessages[]
6. POST /api/release-notes/{task_id}/stages/{stageNum}/refine
   Body: { message, content }
7. Backend builds LLM prompt:
   "You are helping a software engineer refine release documentation..."
   + current content + user request
8. safe_completion(model="gpt-4o", temperature=0.7, max_tokens=4096)
9. Returns { refined_content, message }
10. Assistant message added to refinementMessages[]
11. Chat displays response with "Apply" button
12. User clicks "Apply"
13. InlineRefinementChat calls onApply(msg.content)
14. Parent's handleApplyRefinement(content) called
15. Guard: if (!content || !content.trim()) return
16. setEditableContent(content)
17. For analysis: also update stageDocuments[activeTab]
```

---

## 15. PDF Export

### CSS Stylesheet (`_PDF_CSS`)

```
Page: A4, 2cm margins
Font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial
Body: 11pt, 1.6 line-height, #1a1a1a
H1: 22pt, blue bottom border (#2563eb), #1e293b
H2: 16pt, #334155
H3: 13pt, #475569
Code: #f1f5f9 background, 10pt
Pre: #f8fafc, 1px border, 9.5pt
Table: border-collapse, 10pt, #f1f5f9 header
Blockquote: 4px blue left border, #f8fafc background
```

### Conversion Pipeline

```
Markdown content (from DB or file)
    ↓
markdown.markdown(content, extensions=["tables", "fenced_code", "codehilite", "toc", "sane_lists"])
    ↓
HTML body
    ↓
Wrap in <!DOCTYPE html> with _PDF_CSS
    ↓
weasyprint.HTML(string=full_html).write_pdf()
    ↓
Save to {work_dir}/input_files/{repo_name}_{stage_name}[_{doc_key}].pdf
    ↓
FileResponse(media_type="application/pdf")
```

---

## 16. Error Handling & Recovery

### Backend Error Handling

| Scenario | Handling |
|----------|----------|
| Invalid repo URL | `400 Bad Request` — only HTTPS GitHub/GitLab |
| Same base/head branch | `400 Bad Request` |
| Stage already running | `409 Conflict` |
| Stage already completed | `409 Conflict` |
| Prior stages not completed | `400 Bad Request` with stage details |
| Task/stage not found | `404 Not Found` |
| Stage execution failure | Stage marked `"failed"`, error in `error_message`, workflow marked `"failed"` |
| LLM refinement failure | `500 Internal Server Error` with details |
| Git clone failure | `RuntimeError` → stage fails |
| Callback/cost logging failure | Silently logged, does not block execution |
| DB commit failure | `db.rollback()`, re-raise as `500` |

### Frontend Error Handling

| Scenario | Handling |
|----------|----------|
| API call failure | `setError(e.message)` → error banner with dismiss |
| Polling errors | Silently ignored (continue polling) |
| Console poll errors | Silently ignored |
| Empty refinement content | `handleApplyRefinement` guard: `if (!content \|\| !content.trim()) return` |
| `"None"` / `"null"` content | Sanitized in `fetchStageContent()` |

### Task Recovery

- **Resume:** `POST /{task_id}/resume` finds first non-completed stage and re-executes
- **Retry failed stage:** Frontend re-calls `executeStage(stageNum)` after failure
- **Stop:** `POST /{task_id}/stop` cancels background tasks, marks stages failed
- **Stale running detection:** Resume endpoint checks `_running_tasks[bg_key].done()` — if task finished but DB shows "running", treats as retryable

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `backend/routers/releasenotes.py` | ~1655 | All API endpoints, stage execution, git ops, refine, PDF |
| `backend/models/releasenotes_schemas.py` | ~123 | Pydantic request/response models |
| `mars-ui/components/tasks/ReleaseNotesTask.tsx` | ~1221 | React UI (6 sub-components) |
| `mars-ui/hooks/useReleaseNotesTask.ts` | ~317 | React hook (state, API calls, polling) |
| `mars-ui/types/releasenotes.ts` | ~95 | TypeScript types and constants |
| `cmbagent/task_framework/releasenotes_helpers.py` | ~470 | P&C kwargs builders, output builders, extractors |
| `cmbagent/task_framework/releasenotes_oneshot_helpers.py` | ~270 | One-shot kwargs builders |
| `cmbagent/task_framework/prompts/releasenotes/analysis.py` | ~143 | 6 analysis prompts (planner + researcher × 3) |
| `cmbagent/task_framework/prompts/releasenotes/release_notes.py` | ~79 | 2 release notes prompts |
| `cmbagent/task_framework/prompts/releasenotes/migration.py` | ~91 | 2 migration prompts |
| `cmbagent/task_framework/prompts/releasenotes/oneshot.py` | ~208 | 5 one-shot prompts |
