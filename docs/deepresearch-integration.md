# Deepresearch Research Paper Workflow — End-to-End Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Directory Structure](#3-directory-structure)
4. [The 4-Phase Pipeline](#4-the-4-phase-pipeline)
   - 4.1 [Phase 1 — Idea Generation](#41-phase-1--idea-generation)
   - 4.2 [Phase 2 — Method Development](#42-phase-2--method-development)
   - 4.3 [Phase 3 — Experiment Execution](#43-phase-3--experiment-execution)
   - 4.4 [Phase 4 — Paper Generation (LangGraph)](#44-phase-4--paper-generation-langgraph)
5. [Shared State & Context Flow](#5-shared-state--context-flow)
6. [Backend API Reference](#6-backend-api-reference)
   - 6.1 [REST Endpoints](#61-rest-endpoints)
   - 6.2 [WebSocket Endpoint](#62-websocket-endpoint)
   - 6.3 [Pydantic Schemas](#63-pydantic-schemas)
7. [Database Layer](#7-database-layer)
   - 7.1 [Models](#71-models)
   - 7.2 [Repositories](#72-repositories)
   - 7.3 [Session Management](#73-session-management)
8. [Phase Framework Integration (Stage 4 Only)](#8-phase-framework-integration)
   - 8.1 [Base Classes](#81-base-classes)
   - 8.2 [Phase Registry](#82-phase-registry)
   - 8.3 [Execution Manager](#83-execution-manager)
9. [LangGraph Paper Pipeline](#9-langgraph-paper-pipeline)
   - 9.1 [Graph Nodes](#91-graph-nodes)
   - 9.2 [GraphState](#92-graphstate)
   - 9.3 [Journal Presets](#93-journal-presets)
   - 9.4 [Key Manager](#94-key-manager)
10. [Prompt Templates](#10-prompt-templates)
11. [Frontend UI](#11-frontend-ui)
    - 11.1 [Type Definitions](#111-type-definitions)
    - 11.2 [State Management Hook](#112-state-management-hook)
    - 11.3 [Wizard Container](#113-wizard-container)
    - 11.4 [Panel Components](#114-panel-components)
12. [File Upload & Data Handling](#12-file-upload--data-handling)
13. [Console Output & Real-Time Streaming](#13-console-output--real-time-streaming)
14. [Task Resumption](#14-task-resumption)
15. [Cost Tracking & Observability](#15-cost-tracking--observability)
16. [Testing](#16-testing)
17. [Configuration & Model Defaults](#17-configuration--model-defaults)
18. [End-to-End User Flow](#18-end-to-end-user-flow)
19. [Error Handling & Troubleshooting](#19-error-handling--troubleshooting)

---

## 1. Overview

Deepresearch is a **4-stage interactive research paper generation workflow** integrated into CMBAgent as a first-class task mode. It automates the full research pipeline:

1. **Idea Generation** — AI agents brainstorm and refine research ideas
2. **Method Development** — A methodology is designed for the selected idea
3. **Experiment Execution** — Code is generated and executed to produce results and plots
4. **Paper Generation** — A complete academic paper (PDF + LaTeX) is produced

Each stage is human-in-the-loop: users can review, edit, and refine the AI output before proceeding to the next stage. The system is registered under the mode `"deepresearch-research"` and appears in the UI as "Research Paper".

**Key technologies:**
- **Backend:** Python, FastAPI, SQLAlchemy, asyncio
- **AI Orchestration (Stages 1-3):** `planning_and_control_context_carryover` from CMBAgent workflows
- **AI Orchestration (Stage 4):** LangGraph state machine with 10+ nodes
- **Frontend:** React, TypeScript, Next.js
- **Real-time:** WebSocket + REST polling
- **LLM providers:** OpenAI (GPT-4o, GPT-4.1, o3-mini), Google (Gemini 2.5 Flash), Perplexity (citations)

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React/Next.js)                    │
│                                                                     │
│  TaskList.tsx ──► DeepresearchResearchTask.tsx (5-step wizard)           │
│                    ├── SetupPanel.tsx        (Step 0)               │
│                    ├── ReviewPanel.tsx       (Steps 1, 2)           │
│                    ├── ExecutionPanel.tsx    (Step 3)               │
│                    └── PaperPanel.tsx        (Step 4)               │
│                                                                     │
│  useDeepresearchTask.ts ── state management, API calls, WebSocket       │
└───────────┬──────────────────────────────────┬──────────────────────┘
            │ REST API                         │ WebSocket
            ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│                                                                     │
│  routers/deepresearch.py ── REST endpoints + direct execution engine     │
│    Stages 1-3: calls planning_and_control_context_carryover()       │
│                directly with full callbacks (CostCollector,         │
│                EventRepository, print callbacks)                    │
│    Stage 4:    delegates to DeepresearchPaperPhase (LangGraph)           │
│  main.py            ── WebSocket /ws/deepresearch/{task_id}/{stage_num} │
│  routers/__init__.py── registers deepresearch_router                    │
│  routers/files.py   ── file upload endpoint                        │
└───────────┬──────────────────────────────────┬──────────────────────┘
            │                                  │
            ▼                                  ▼
┌────────────────────────┐    ┌───────────────────────────────────────┐
│     DATABASE (SQLite)  │    │      PHASE EXECUTION ENGINE           │
│                        │    │                                       │
│  WorkflowRun           │    │  Stages 1-3 (direct from router):    │
│  TaskStage             │    │    planning_and_control_context_       │
│  Session               │    │    carryover() with callbacks=         │
│  CostRecord            │    │    + CostCollector + EventRepository   │
│                        │    │    + stage_helpers.py (prompts, post-  │
│  TaskStageRepository   │    │      processing, file I/O)            │
│  CostRepository        │    │                                       │
│  EventRepository       │    │  Stage 4:                             │
└────────────────────────┘    │    DeepresearchPaperPhase (LangGraph)      │
                              │    build_graph() pipeline              │
                              │    (preprocess → keywords → abstract  │
                              │     → intro → methods → results       │
                              │     → conclusions → plots → refine    │
                              │     → citations → END)                │
                              └───────────────────────────────────────┘
```

---

## 3. Directory Structure

```
cmbagent/
├── backend/
│   ├── main.py                              # FastAPI app, WS endpoints
│   ├── core/
│   │   ├── app.py                           # App factory
│   │   └── config.py                        # Settings (default_work_dir, etc.)
│   ├── models/
│   │   └── deepresearch_schemas.py               # Pydantic request/response schemas
│   ├── routers/
│   │   ├── __init__.py                      # Router registration
│   │   ├── deepresearch.py                       # Deepresearch REST API (808 lines)
│   │   └── files.py                         # File upload/download API
│   ├── services/
│   │   └── session_manager.py               # Backend session lifecycle
│   └── websocket/
│       ├── events.py                        # send_ws_event() utility
│       └── handlers.py                      # Generic WS handler
│
├── cmbagent/
│   ├── database/
│   │   ├── base.py                          # init_database(), get_db_session()
│   │   ├── models.py                        # WorkflowRun, TaskStage, Session, etc.
│   │   ├── repository.py                    # TaskStageRepository, CostRepository
│   │   └── session_manager.py               # DB-layer session manager
│   ├── phases/
│   │   ├── base.py                          # Phase, PhaseContext, PhaseResult, PhaseConfig
│   │   ├── registry.py                      # PhaseRegistry
│   │   ├── execution_manager.py             # PhaseExecutionManager
│   │   └── context.py                       # WorkflowContext
│   ├── workflows/
│   │   └── planning_control.py              # planning_and_control_context_carryover()
│   └── task_framework/
│       ├── __init__.py                      # Exports utils + stage_helpers
│       ├── config.py                        # Constants (INPUT_FILES, file names, paths)
│       ├── utils.py                         # get_task_result(), extract_clean_markdown()
│       ├── stage_helpers.py                 # Pure functions for stages 1-3 (prompts, extraction, file I/O)
│       ├── key_manager.py                   # KeyManager (API keys)
│       ├── phases/
│       │   └── paper.py                     # DeepresearchPaperPhase (only phase class retained)
│       ├── prompts/
│       │   └── deepresearch/
│       │       ├── __init__.py
│       │       ├── idea.py                  # idea_planner_prompt
│       │       ├── method.py                # method_planner_prompt, method_researcher_prompt
│       │       └── experiment.py            # experiment_planner/engineer/researcher prompts
│       └── paper_agents/
│           ├── __init__.py
│           ├── agents_graph.py              # build_graph() — LangGraph pipeline
│           ├── parameters.py                # GraphState, FILES, PAPER, LLM TypedDicts
│           ├── journal.py                   # Journal enum, LatexPresets
│           ├── routers.py                   # citation_router conditional edge
│           ├── reader.py                    # preprocess_node
│           ├── paper_node.py                # All section-writing nodes
│           └── LaTeX/                       # Journal-specific templates (.cls, .bst, .sty)
│
├── mars-ui/
│   ├── app/tasks/page.tsx                   # Task routing page
│   ├── types/deepresearch.ts                     # TypeScript type definitions
│   ├── hooks/useDeepresearchTask.ts              # React hook for Deepresearch state management
│   ├── components/
│   │   ├── tasks/
│   │   │   ├── TaskList.tsx                 # Task catalog (lists "Research Paper")
│   │   │   └── DeepresearchResearchTask.tsx      # Main wizard container
│   │   └── deepresearch/
│   │       ├── SetupPanel.tsx               # Step 0: Research description + file upload
│   │       ├── ReviewPanel.tsx              # Steps 1-2: Edit/preview + refinement chat
│   │       ├── ExecutionPanel.tsx           # Step 3: Live console output
│   │       ├── PaperPanel.tsx               # Step 4: Download artifacts
│   │       ├── RefinementChat.tsx           # AI chat sidebar for content editing
│   │       ├── FileUploadZone.tsx           # Drag-and-drop file uploads
│   │       └── ExecutionProgress.tsx        # Console output display component
│   └── lib/config.ts                        # getApiUrl(), getWsUrl()
│
├── tests/
│   ├── test_deepresearch_api.py                  # REST endpoint tests
│   ├── test_deepresearch_phases.py               # Stage helper unit tests + paper phase tests
│   └── test_deepresearch_integration.py          # Full context flow integration tests
│
└── cmbagent_workdir/
    └── deepresearch_tasks/
        └── {task_id}/                       # Per-task working directory
            ├── input_files/
            │   ├── data_description.md
            │   ├── idea.md
            │   ├── methods.md
            │   ├── results.md
            │   ├── plots/
            │   └── [user-uploaded files]
            ├── idea/                        # Stage 1 working directory
            ├── method/                      # Stage 2 working directory
            ├── experiment/                  # Stage 3 working directory
            └── paper/                       # Stage 4 output
                ├── paper_v1_preliminary.tex/.pdf
                ├── paper_v2_no_citations.tex/.pdf
                ├── paper_v3_citations.tex/.pdf
                └── paper_v4_final.tex/.pdf
```

---

## 4. The 4-Phase Pipeline

### 4.1 Phase 1 — Idea Generation

**Helper functions:** `cmbagent/task_framework/stage_helpers.py`
**Invoked from:** `backend/routers/deepresearch.py` → `_run_planning_control_stage()`

**What it does:**
Uses a multi-agent debate pattern to generate and refine research ideas. Called directly via `planning_and_control_context_carryover()` with full callback infrastructure (no phase wrapper class).

**Agent flow (defined in `idea_planner_prompt`):**
1. `idea_maker` generates 5 research project ideas related to the data
2. `idea_hater` critiques the 5 ideas
3. `idea_maker` selects and improves the best 2 ideas based on critique
4. `idea_hater` critiques the 2 improved ideas
5. `idea_maker` selects the single best idea
6. `idea_maker` writes a scientific paper title + 5-sentence description

**Default model configuration (`IDEA_DEFAULTS` in `stage_helpers.py`):**

| Parameter | Default | Description |
|---|---|---|
| `idea_maker_model` | `gpt-4o` | Model for the idea generation agent |
| `idea_hater_model` | `o3-mini` | Model for the critique agent |
| `planner_model` | `gpt-4o` | Model for the planning agent |
| `plan_reviewer_model` | `o3-mini` | Model for plan review |
| `orchestration_model` | `gpt-4.1` | Default LLM for orchestration |
| `formatter_model` | `o3-mini` | Model for response formatting |

**Execution parameters:** `max_plan_steps=6`, `n_plan_reviews=1`

**Helper functions used:**
- `build_idea_kwargs()` — Builds the kwargs dict for `planning_and_control_context_carryover`
- `extract_idea_result()` — Extracts text from `idea_maker_nest` agent, applies regex post-processing
- `save_idea()` — Writes `input_files/idea.md`
- `build_idea_output()` — Returns `output_data` dict for DB storage

**Output:**
- `shared_state`: `{ research_idea, data_description }`
- File: `input_files/idea.md`

---

### 4.2 Phase 2 — Method Development

**Helper functions:** `cmbagent/task_framework/stage_helpers.py`
**Invoked from:** `backend/routers/deepresearch.py` → `_run_planning_control_stage()`

**What it does:**
Develops a detailed research methodology based on the idea from Phase 1.

**Agent flow (defined in `method_planner_prompt` and `method_researcher_prompt`):**
1. The `researcher` provides reasoning relevant to the project idea
2. Specific hypotheses, assumptions, and questions are clarified
3. A multi-step methodology is designed (methods + workflow only, no future directions)
4. The final step writes the full Methodology description (~500 words, markdown format)

**Default model configuration (`METHOD_DEFAULTS` in `stage_helpers.py`):**

| Parameter | Default | Description |
|---|---|---|
| `researcher_model` | `gpt-4.1` | Model for the researcher agent |
| `planner_model` | `gpt-4.1` | Model for the planning agent |
| `plan_reviewer_model` | `o3-mini` | Model for plan review |
| `orchestration_model` | `gpt-4.1` | Default LLM for orchestration |
| `formatter_model` | `o3-mini` | Model for response formatting |

**Execution parameters:** `max_plan_steps=4`, `max_n_attempts=4`, `n_plan_reviews=1`

**Helper functions used:**
- `build_method_kwargs()` — Formats `method_planner_prompt` and `method_researcher_prompt` with `{research_idea}`
- `extract_method_result()` — Extracts from `researcher_response_formatter` + `extract_clean_markdown()`
- `save_method()` — Writes `input_files/methods.md`
- `build_method_output()` — Returns `output_data` dict for DB storage

**Input requirements:** `research_idea` must exist in shared_state (from Phase 1).

**Output:**
- `shared_state`: `{ research_idea, data_description, methodology }`
- File: `input_files/methods.md`

---

### 4.3 Phase 3 — Experiment Execution

**Helper functions:** `cmbagent/task_framework/stage_helpers.py`
**Invoked from:** `backend/routers/deepresearch.py` → `_run_planning_control_stage()`

**What it does:**
Executes the research experiments: generates and runs code, produces plots and quantitative results.

**Agent flow (defined in 3 prompts: planner, engineer, researcher):**
1. The `planner` creates an execution plan involving `engineer` and `researcher` agents
2. The `engineer` writes and executes code to generate results, plots, and key statistics
3. The `researcher` produces a detailed ~2000-word results discussion with interpretations

**Default model configuration (`EXPERIMENT_DEFAULTS` in `stage_helpers.py`):**

| Parameter | Default | Description |
|---|---|---|
| `engineer_model` | `gpt-4.1` | Model for the code execution agent |
| `researcher_model` | `o3-mini` | Model for the researcher agent |
| `planner_model` | `gpt-4o` | Model for the planning agent |
| `plan_reviewer_model` | `o3-mini` | Model for plan review |
| `orchestration_model` | `gpt-4.1` | Default LLM for orchestration |
| `formatter_model` | `o3-mini` | Model for response formatting |

**Execution parameters:** `max_n_attempts=10`, `max_n_steps=6`, `max_rounds_control=500`, `restart_at_step=-1`

**Helper functions used:**
- `build_experiment_kwargs()` — Formats 3 prompts with `{research_idea}`, `{methodology}`, `{involved_agents_str}`
- `extract_experiment_result()` — Extracts results text + `displayed_images` from `final_context`
- `save_experiment()` — Writes `input_files/results.md`, moves plots to `input_files/plots/`
- `build_experiment_output()` — Returns `output_data` dict for DB storage

**Key details:**
- The engineer is instructed to print all quantitative information to console (the researcher cannot read files)
- Plot paths come from `final_context['displayed_images']` (not glob)
- Plots are moved to `input_files/plots/` for the paper stage
- Existing plots in the directory are cleared before writing new ones
- If the planner LLM returns `{"sub_tasks": []}` (empty plan), the planning phase **fails immediately** with a clear error rather than silently succeeding and causing a confusing downstream error (see [Section 19](#19-error-handling--troubleshooting))

**Input requirements:** Both `research_idea` and `methodology` must exist in shared_state.

**Output:**
- `shared_state`: `{ research_idea, data_description, methodology, results, plot_paths }`
- Files: `input_files/results.md`, `input_files/plots/`

---

### 4.4 Phase 4 — Paper Generation (LangGraph)

**File:** `cmbagent/task_framework/phases/paper.py`
**Phase class:** `DeepresearchPaperPhase`
**Registered as:** `deepresearch_paper`

**What it does:**
Generates a complete academic paper using a LangGraph state machine. Unlike Stages 1-3 which call `planning_and_control_context_carryover()` directly via `stage_helpers`, Stage 4 uses a `Phase` subclass (`DeepresearchPaperPhase`) with a dedicated LangGraph pipeline. This is the only Deepresearch stage that uses the Phase framework.

**Configuration (`DeepresearchPaperPhaseConfig`):**

| Parameter | Default | Description |
|---|---|---|
| `llm_model` | `gemini-2.5-flash` | LLM for all paper writing nodes |
| `llm_temperature` | `0.7` | Temperature for generation |
| `llm_max_output_tokens` | `65536` | Max output tokens |
| `writer` | `scientist` | Writing persona |
| `journal` | `None` (Journal.NONE) | Target journal format |
| `add_citations` | `True` | Whether to add citations |
| `cmbagent_keywords` | `False` | Use CMBAgent keyword extraction |

**Input requirements:** The `input_files/` directory must exist (populated by Phases 1-3).

**Output:**
- Files in the `paper/` directory:
  - `paper_v1_preliminary.tex/.pdf` — Initial draft
  - `paper_v2_no_citations.tex/.pdf` — Refined without citations
  - `paper_v3_citations.tex/.pdf` — With citations added
  - `paper_v4_final.tex/.pdf` — Final polished version

See [Section 9](#9-langgraph-paper-pipeline) for detailed LangGraph pipeline documentation.

---

## 5. Shared State & Context Flow

The Deepresearch workflow uses a **cumulative shared state** pattern. Each phase reads context from all previous phases and adds its own output:

```
Phase 1 (Idea)
  Input:  data_description (from user)
  Output: { research_idea, data_description }
     │
     ▼
Phase 2 (Method)
  Input:  shared_state.research_idea
  Output: { research_idea, data_description, methodology }
     │
     ▼
Phase 3 (Experiment)
  Input:  shared_state.research_idea + shared_state.methodology
  Output: { research_idea, data_description, methodology, results, plot_paths }
     │
     ▼
Phase 4 (Paper)
  Input:  reads from input_files/ directory (idea.md, methods.md, results.md, plots/)
  Output: paper/ directory (v1-v4 PDFs + LaTeX)
```

**How shared state is reconstructed between stages:**

The function `build_shared_state()` in `routers/deepresearch.py:100-113` reconstructs the cumulative shared state before each phase execution:

```python
def build_shared_state(task_id, up_to_stage, db, session_id):
    """Accumulate output_data['shared'] from all completed stages
    prior to the current stage."""
    repo = _get_stage_repo(db, session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared
```

This means each stage's `output_data["shared"]` is merged into a single dictionary, with later stages overwriting earlier values if keys overlap.

---

## 6. Backend API Reference

### 6.1 REST Endpoints

All endpoints are prefixed with `/api/deepresearch/`.

**Source:** `backend/routers/deepresearch.py`

#### `POST /api/deepresearch/create`

Creates a new Deepresearch research task with 4 pending stages.

**Request body (`DeepresearchCreateRequest`):**
```json
{
  "task": "Research description / pitch",
  "data_description": "Optional description of uploaded data",
  "config": {}
}
```

**Response (`DeepresearchCreateResponse`):**
```json
{
  "task_id": "uuid",
  "work_dir": "/path/to/deepresearch_tasks/{task_id}",
  "stages": [
    { "stage_number": 1, "stage_name": "idea_generation", "status": "pending", ... },
    { "stage_number": 2, "stage_name": "method_development", "status": "pending", ... },
    { "stage_number": 3, "stage_name": "experiment_execution", "status": "pending", ... },
    { "stage_number": 4, "stage_name": "paper_generation", "status": "pending", ... }
  ]
}
```

**What it does internally:**
1. Generates a UUID for the task
2. Creates the work directory: `{default_work_dir}/deepresearch_tasks/{task_id}/input_files/`
3. Creates a `Session` via `SessionManager` with `mode="deepresearch-research"`
4. Creates a `WorkflowRun` record with `mode="deepresearch-research"`, `status="executing"`
5. Creates 4 `TaskStage` records (one per phase) with `status="pending"`
6. Writes `data_description.md` to `input_files/`

---

#### `POST /api/deepresearch/{task_id}/stages/{stage_num}/execute`

Triggers background execution of a single Deepresearch phase.

**Request body (`DeepresearchExecuteRequest`, optional):**
```json
{
  "config_overrides": {}
}
```

**Response:**
```json
{
  "status": "executing",
  "stage_num": 1,
  "task_id": "uuid"
}
```

**Validation:**
- `stage_num` must be 1-4
- Stage must not already be running or completed
- All previous stages must be completed (strict ordering)

**What it does internally:**
1. Looks up the `WorkflowRun` to get `work_dir`, `task_description`, `data_description`
2. Enhances `data_description` with file context from uploaded files (`_build_file_context()`)
3. Reconstructs `shared_state` from all completed prior stages (`build_shared_state()`)
4. Marks the stage as `"running"` in the database
5. Launches the appropriate background task as an `asyncio.Task`:
   - **Stages 1-3:** `_run_planning_control_stage()` — calls `planning_and_control_context_carryover()` directly with full callbacks
   - **Stage 4:** `_run_paper_stage()` — delegates to `DeepresearchPaperPhase`
6. Returns immediately

**Background execution (Stages 1-3 — `_run_planning_control_stage()`):**
1. Creates `CostCollector(db_session, session_id, run_id=task_id)` for per-LLM-call cost tracking
2. Creates `EventRepository(db, session_id)` for execution event logging
3. Builds `WorkflowCallbacks` with:
   - `on_agent_message` → writes `ExecutionEvent(type="agent_call")`
   - `on_code_execution` → writes `ExecutionEvent(type="code_exec")`
   - `on_tool_call` → writes `ExecutionEvent(type="tool_call")`
   - `on_cost_update` → calls `cost_collector.collect_from_callback(cost_data)`
4. Merges callbacks with `create_print_callbacks()` via `merge_callbacks()`
5. Calls `stage_helpers.build_*_kwargs()` to build all arguments (prompts, models, paths)
6. Captures stdout/stderr via `_ConsoleCapture` (thread-safe)
7. Calls `asyncio.to_thread(planning_and_control_context_carryover, task, **kwargs)` with `callbacks=` injected
8. Calls `stage_helpers.extract_*_result()`, `save_*()`, `build_*_output()`
9. `cost_collector.collect_from_work_dir(work_dir)` as safety net for any costs missed by callbacks
10. On success: updates stage status to `"completed"` with `output_data`
11. On failure: updates stage status to `"failed"` with `error_message`

**Background execution (Stage 4 — `_run_paper_stage()`):**
1. Creates a `PhaseContext` with the accumulated shared state
2. Captures stdout/stderr via `_ConsoleCapture`
3. Calls `DeepresearchPaperPhase().execute(context)` (awaited)
4. On success: updates stage status to `"completed"` with `output_data`
5. On failure: updates stage status to `"failed"` with `error_message`

---

#### `GET /api/deepresearch/{task_id}/stages/{stage_num}/content`

Gets the output content for a completed stage.

**Response (`DeepresearchStageContentResponse`):**
```json
{
  "stage_number": 1,
  "stage_name": "idea_generation",
  "status": "completed",
  "content": "The generated research idea text...",
  "shared_state": { "research_idea": "...", "data_description": "..." },
  "output_files": ["input_files/idea.md"]
}
```

**Content resolution priority:**
1. `output_data["shared"][shared_key]` from the database
2. Fallback: read the `.md` file from disk (`idea.md`, `methods.md`, `results.md`)

---

#### `PUT /api/deepresearch/{task_id}/stages/{stage_num}/content`

Saves user edits to a stage's content.

**Request body (`DeepresearchContentUpdateRequest`):**
```json
{
  "content": "Updated markdown content",
  "field": "research_idea"
}
```

**What it does:**
1. Updates `output_data["shared"][field]` in the database
2. Writes the updated content to the corresponding `.md` file on disk
3. Both updates ensure the next stage reads the edited version

---

#### `POST /api/deepresearch/{task_id}/stages/{stage_num}/refine`

Uses an LLM to refine stage content based on user instruction.

**Request body (`DeepresearchRefineRequest`):**
```json
{
  "message": "Make the methodology section more specific",
  "content": "Current editor content..."
}
```

**Response (`DeepresearchRefineResponse`):**
```json
{
  "refined_content": "The refined version...",
  "message": "Content refined successfully"
}
```

**What it does:**
- Makes a single GPT-4o call with a prompt containing the current content and the user's refinement instruction
- Returns only the refined content for the user to review and optionally apply

---

#### `GET /api/deepresearch/{task_id}/stages/{stage_num}/console`

Gets console output lines for a running stage (REST polling fallback).

**Query parameters:**
- `since` (int, default 0): Line index to start from for incremental fetching

**Response:**
```json
{
  "lines": ["Starting idea_generation...", "Phase deepresearch_idea initialized..."],
  "next_index": 42,
  "stage_num": 1
}
```

---

#### `GET /api/deepresearch/recent`

Lists incomplete Deepresearch tasks for the resume flow.

**Response:** Array of `DeepresearchRecentTaskResponse`:
```json
[
  {
    "task_id": "uuid",
    "task": "Research description",
    "status": "executing",
    "created_at": "2025-01-15T10:30:00Z",
    "current_stage": 2,
    "progress_percent": 25.0
  }
]
```

---

#### `GET /api/deepresearch/{task_id}`

Gets full task state including all stages, costs, and progress.

**Response (`DeepresearchTaskStateResponse`):**
```json
{
  "task_id": "uuid",
  "task": "Research description",
  "status": "executing",
  "work_dir": "/path/to/deepresearch_tasks/{task_id}",
  "created_at": "2025-01-15T10:30:00Z",
  "stages": [ ... ],
  "current_stage": 2,
  "progress_percent": 25.0,
  "total_cost_usd": 0.0542
}
```

---

### 6.2 WebSocket Endpoint

**URL:** `ws://host/ws/deepresearch/{task_id}/{stage_num}`

**Source:** `backend/main.py:52-128`

Streams real-time console output from the shared buffer and sends completion/failure events.

**Event types sent:**

| Event | Data | When |
|---|---|---|
| `status` | `{ message, stage_num }` | On connection |
| `console_output` | `{ text, stage_num }` | Every 1s poll of console buffer |
| `stage_completed` | `{ stage_num, stage_name }` | When stage finishes successfully |
| `stage_failed` | `{ stage_num, error }` | When stage fails |

**Lifecycle:**
1. Accepts the WebSocket connection
2. Polls the shared console buffer (`_console_buffers`) every 1 second
3. Sends new lines as `console_output` events
4. Checks the database for stage completion/failure each cycle
5. On completion: flushes remaining console lines, sends event, clears buffer, closes
6. On failure: flushes remaining lines, sends error event, clears buffer, closes

---

### 6.3 Pydantic Schemas

**Source:** `backend/models/deepresearch_schemas.py`

| Schema | Type | Description |
|---|---|---|
| `DeepresearchStageStatus` | Enum | `pending`, `running`, `completed`, `failed` |
| `DeepresearchCreateRequest` | Request | `task`, `data_description?`, `config?` |
| `DeepresearchExecuteRequest` | Request | `config_overrides?` |
| `DeepresearchContentUpdateRequest` | Request | `content`, `field` |
| `DeepresearchRefineRequest` | Request | `message`, `content` |
| `DeepresearchStageResponse` | Response | `stage_number`, `stage_name`, `status`, timing, `error` |
| `DeepresearchCreateResponse` | Response | `task_id`, `work_dir`, `stages[]` |
| `DeepresearchStageContentResponse` | Response | `stage_number`, `status`, `content`, `shared_state`, `output_files` |
| `DeepresearchRefineResponse` | Response | `refined_content`, `message` |
| `DeepresearchTaskStateResponse` | Response | Full task state with stages, progress, cost |
| `DeepresearchRecentTaskResponse` | Response | Summary for resume flow |

---

## 7. Database Layer

### 7.1 Models

**Source:** `cmbagent/database/models.py`

#### WorkflowRun

The parent record for a Deepresearch task.

| Column | Type | Deepresearch Usage |
|---|---|---|
| `id` | String (UUID) | Task ID |
| `session_id` | String (FK) | Links to Session |
| `mode` | String | `"deepresearch-research"` |
| `agent` | String | `"planner"` |
| `model` | String | `"gpt-4o"` |
| `status` | String | `"executing"` → `"completed"` / `"failed"` |
| `task_description` | String | User's research description |
| `started_at` | DateTime | Creation timestamp |
| `meta` | JSON | `{ work_dir, data_description, config, session_id }` |
| `parent_run_id` | String (FK) | `None` for parent runs |

#### TaskStage

Individual stage tracking within a multi-stage task.

| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-increment |
| `parent_run_id` | String (FK) | Links to WorkflowRun.id |
| `stage_number` | Integer | 1-4 |
| `stage_name` | String | `idea_generation`, `method_development`, `experiment_execution`, `paper_generation` |
| `status` | String | `pending` → `running` → `completed` / `failed` |
| `input_data` | JSON | `{ task, data_description }` |
| `output_data` | JSON | `{ shared: { research_idea, ... }, artifacts: { ... }, chat_history: [...] }` |
| `output_files` | JSON (list) | File paths of generated artifacts |
| `error_message` | String | Error text if failed |
| `started_at` | DateTime | Execution start |
| `completed_at` | DateTime | Execution end |

---

### 7.2 Repositories

**Source:** `cmbagent/database/repository.py`

#### TaskStageRepository

| Method | Description |
|---|---|
| `create_stage(parent_run_id, stage_number, stage_name, status, input_data)` | Create a new stage record |
| `list_stages(parent_run_id)` | List all stages for a task, ordered by stage_number |
| `get_current_stage(parent_run_id)` | Get the first non-completed stage |
| `update_stage_status(stage_id, status, output_data?, output_files?, error_message?)` | Update stage status and data |
| `get_task_progress(parent_run_id)` | Get progress stats (completed count, total, percent) |

#### CostRepository

| Method | Description |
|---|---|
| `record_cost(parent_run_id, model, input_tokens, output_tokens, cost_usd, ...)` | Record a cost entry |
| `get_run_cost(run_id)` | Get cost for a single run |
| `get_task_total_cost(parent_run_id)` | Get total cost across all stages |
| `get_session_cost(session_id)` | Get cost for entire session |

---

### 7.3 Session Management

**Source:** `backend/services/session_manager.py`

When a Deepresearch task is created, a session is created via `SessionManager.create_session()`:

```python
session_id = sm.create_session(
    mode="deepresearch-research",
    config={"task_id": task_id, "work_dir": work_dir},
    name=f"Deepresearch: {request.task[:60]}",
)
```

The session groups all workflow runs, cost records, and stages for a single Deepresearch task. It supports:
- `save_session_state()` / `load_session_state()` for state persistence
- `suspend_session()` / `resume_session()` for task resumption
- Background cleanup of expired sessions

---

## 8. Phase Framework Integration

> **Note:** Only Stage 4 (Paper Generation) uses the Phase framework. Stages 1-3 call
> `planning_and_control_context_carryover()` directly from the router with full callback
> infrastructure, using pure helper functions in `stage_helpers.py` for prompt formatting,
> result extraction, and file I/O. This avoids unnecessary abstraction while preserving
> full observability (cost tracking, event logging, console streaming).

### 8.1 Base Classes

**Source:** `cmbagent/phases/base.py`

#### PhaseContext

The context object used by `DeepresearchPaperPhase` (Stage 4 only):

```python
@dataclass
class PhaseContext:
    workflow_id: str       # "deepresearch-{task_id}"
    run_id: str            # task_id
    phase_id: str          # "stage-{N}"
    task: str              # User's research description
    work_dir: str          # Per-task working directory
    shared_state: dict     # Accumulated context from prior stages
    api_keys: dict         # API keys
    callbacks: Any         # Optional callback handlers
    input_data: dict       # Phase-specific input
    output_data: dict      # Phase output (populated during execution)
```

#### PhaseResult

Returned by `DeepresearchPaperPhase.execute()`:

```python
@dataclass
class PhaseResult:
    status: PhaseStatus    # COMPLETED or FAILED
    context: PhaseContext   # Updated context with output_data
    error: str | None      # Error message if failed
    chat_history: list     # Agent conversation history
```

### 8.2 Phase Registry

**Source:** `cmbagent/phases/registry.py`

Only `DeepresearchPaperPhase` is registered:

```python
@PhaseRegistry.register("deepresearch_paper")
class DeepresearchPaperPhase(Phase):
    ...
```

The registry provides:
- `PhaseRegistry.get(phase_type)` — Returns the phase class
- `PhaseRegistry.create(phase_type, config)` — Instantiates a phase
- `PhaseRegistry.list_all()` — Lists all registered phases
- `PhaseRegistry.is_registered(phase_type)` — Checks registration

The router uses `DeepresearchPaperPhase` directly (imported) for Stage 4 only. Stages 1-3 bypass the Phase framework entirely.

---

### 8.3 Execution Manager

**Source:** `cmbagent/phases/execution_manager.py`

`PhaseExecutionManager` provides lifecycle management for phase execution:

| Method | Description |
|---|---|
| `start()` | Begin phase execution, set timers |
| `complete(output_data)` | Mark phase complete, return `PhaseResult` |
| `fail(error, traceback)` | Mark phase failed, return `PhaseResult` |
| `start_step(num, description)` | Begin a named sub-step |
| `complete_step(num, message)` | Complete a sub-step |
| `log_event(type, data)` | Log execution events |
| `save_checkpoint(data)` | Save execution checkpoint |
| `check_should_continue()` | Check for pause/cancel requests |

---

## 9. LangGraph Paper Pipeline

### 9.1 Graph Nodes

**Source:** `cmbagent/task_framework/paper_agents/agents_graph.py`

The paper generation pipeline is a LangGraph `StateGraph` with 10 nodes executed in sequence:

```
START
  │
  ▼
preprocess_node    ── Initialize LLM, file paths, LaTeX setup, load input files
  │
  ▼
keywords_node      ── Extract keywords from idea + methods + results
  │
  ▼
abstract_node      ── Generate title and abstract with self-reflection
  │
  ▼
introduction_node  ── Write Introduction section
  │
  ▼
methods_node       ── Write Methods section
  │
  ▼
results_node       ── Write Results section
  │
  ▼
conclusions_node   ── Write Conclusions section
  │
  ▼
plots_node         ── Process images, generate figure captions (batches of 7, max 25)
  │
  ▼
refine_results     ── Improve Results section with figure references
  │
  ▼
citation_router    ── Conditional: add_citations?
  ├── True ──► citations_node ──► END
  └── False ──────────────────► END
```

**Paper versions generated:**
1. `paper_v1_preliminary` — After all section nodes complete
2. `paper_v2_no_citations` — After plots and refinement
3. `paper_v3_citations` — After citations are added
4. `paper_v4_final` — Final polished version

The graph uses `MemorySaver` as a checkpointer and requires a `thread_id` in the config:

```python
config = {
    "configurable": {"thread_id": "1"},
    "recursion_limit": 100,
}
```

---

### 9.2 GraphState

**Source:** `cmbagent/task_framework/paper_agents/parameters.py`

```python
class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # LangGraph message history
    files: FILES          # File paths (Folder, Idea, Methods, Results, Plots, Paper versions)
    idea: IDEA            # Parsed idea, methods, results text
    paper: PAPER          # Paper sections (Title, Abstract, Keywords, Intro, etc.)
    tokens: TOKENS        # Token usage tracking (input/output)
    llm: LLM             # LLM config (model, temperature, max_output_tokens)
    latex: LATEX          # LaTeX state (section_to_fix)
    keys: KeyManager      # API keys
    time: TIME            # Timing (start timestamp)
    writer: str           # Writing persona (e.g., "scientist")
    params: PARAMS        # Additional parameters (num_keywords)
```

The `preprocess_node` initializes most of these fields from the input state and the `input_files/` directory.

---

### 9.3 Journal Presets

**Source:** `cmbagent/task_framework/paper_agents/journal.py`

Supported journals:

| Journal | Description |
|---|---|
| `Journal.NONE` | Standard LaTeX with `unsrt` bibliography |
| `Journal.AAS` | American Astronomical Society (ApJ, etc.) |
| `Journal.APS` | American Physical Society (PRL, PRA, etc.) |
| `Journal.ICML` | Int'l Conference on Machine Learning |
| `Journal.JHEP` | Journal of High Energy Physics |
| `Journal.NeurIPS` | Conference on Neural Information Processing |
| `Journal.PASJ` | Publications of the Astronomical Society of Japan |

Each journal has a `LatexPresets` configuration specifying the article class, layout, title/author commands, bibliography style, and required packages.

---

### 9.4 Key Manager

**Source:** `cmbagent/task_framework/key_manager.py`

```python
class KeyManager(BaseModel):
    ANTHROPIC: str | None = ""
    GEMINI: str | None = ""
    OPENAI: str | None = ""
    PERPLEXITY: str | None = ""
    SEMANTIC_SCHOLAR: str | None = ""
```

Loads keys from environment variables via `get_keys_from_env()`:
- `OPENAI_API_KEY` → `OPENAI`
- `GOOGLE_API_KEY` → `GEMINI`
- `ANTHROPIC_API_KEY` → `ANTHROPIC`
- `PERPLEXITY_API_KEY` → `PERPLEXITY` (used for citations)
- `SEMANTIC_SCHOLAR_KEY` → `SEMANTIC_SCHOLAR` (used for fast paper search)

---

## 10. Prompt Templates

**Source:** `cmbagent/task_framework/prompts/deepresearch/`

### Idea Phase (`idea.py`)

```
idea_planner_prompt:
- Ask idea_maker to generate 5 research project ideas
- Ask idea_hater to critique them
- Select and improve the best 2
- Critique again
- Select the single best idea
- Report as: scientific paper title + 5-sentence description
```

### Method Phase (`method.py`)

Two prompts, both injected with `{research_idea}`:

- `method_planner_prompt`: Instructs multi-step methodology design (no future directions, no calculations)
- `method_researcher_prompt`: Write a ~500-word methodology in markdown format, as a senior researcher explaining to an assistant

### Experiment Phase (`experiment.py`)

Three prompts, all injected with `{research_idea}` and `{methodology}`:

- `experiment_planner_prompt`: Create an execution plan using `{involved_agents_str}` agents; final step must write the full Results section
- `experiment_engineer_prompt`: Generate code for results, plots, and statistics; print all quantitative info to console (researcher can't read files)
- `experiment_researcher_prompt`: Write a ~2000-word results discussion in academic style

---

## 11. Frontend UI

### 11.1 Type Definitions

**Source:** `mars-ui/types/deepresearch.ts`

Key types:

```typescript
type DeepresearchStageStatus = 'pending' | 'running' | 'completed' | 'failed'
type DeepresearchWizardStep = 0 | 1 | 2 | 3 | 4
// 0=Setup, 1=Idea Review, 2=Method Review, 3=Experiment, 4=Paper

interface DeepresearchTaskState {
  task_id: string
  stages: DeepresearchStage[]
  current_stage?: number
  progress_percent: number
  total_cost_usd?: number
}
```

Mappings:

```typescript
WIZARD_STEP_TO_STAGE = { 0: null, 1: 1, 2: 2, 3: 3, 4: 4 }
STAGE_SHARED_KEYS = { 1: 'research_idea', 2: 'methodology', 3: 'results' }
```

---

### 11.2 State Management Hook

**Source:** `mars-ui/hooks/useDeepresearchTask.ts`

The `useDeepresearchTask()` hook encapsulates all Deepresearch client-side logic:

| Returned State | Type | Description |
|---|---|---|
| `taskId` | `string \| null` | Current task UUID |
| `taskState` | `DeepresearchTaskState \| null` | Full task state from API |
| `currentStep` | `DeepresearchWizardStep` | Current wizard step (0-4) |
| `isLoading` | `boolean` | Task creation in progress |
| `error` | `string \| null` | Current error message |
| `editableContent` | `string` | Editor content for review panels |
| `refinementMessages` | `RefinementMessage[]` | Chat history for refinement |
| `consoleOutput` | `string[]` | Console output lines |
| `isExecuting` | `boolean` | Stage execution in progress |
| `uploadedFiles` | `UploadedFile[]` | Uploaded file status |

| Returned Action | Description |
|---|---|
| `createTask(task, dataDesc?, config?)` | POST to `/api/deepresearch/create` |
| `executeStage(stageNum)` | POST to execute, connect WS + polls |
| `fetchStageContent(stageNum)` | GET stage content, populate editor |
| `saveStageContent(stageNum, content, field)` | PUT updated content |
| `refineContent(stageNum, message, content)` | POST refinement request |
| `uploadFile(file)` | Upload to `/api/files/upload` |
| `resumeTask(taskId)` | Load task state and restore wizard position |

**Real-time monitoring strategy:**
1. **WebSocket** (`connectWs`) — Listens for `stage_completed` / `stage_failed` events
2. **Status polling** (`startPolling`) — Polls task state every 5 seconds as fallback
3. **Console polling** (`startConsolePoll`) — Polls console output every 2 seconds via REST

---

### 11.3 Wizard Container

**Source:** `mars-ui/components/tasks/DeepresearchResearchTask.tsx`

The main component renders a 5-step wizard using a `Stepper` component:

| Step | Panel Component | Stage |
|---|---|---|
| 0 | `SetupPanel` | — (no stage) |
| 1 | `ReviewPanel` (stageNum=1, sharedKey="research_idea") | Idea Generation |
| 2 | `ReviewPanel` (stageNum=2, sharedKey="methodology") | Method Development |
| 3 | `ExecutionPanel` (stageNum=3) | Experiment Execution |
| 4 | `PaperPanel` (stageNum=4) | Paper Generation |

The stepper dynamically reflects real stage statuses from `taskState`.

---

### 11.4 Panel Components

**Source:** `mars-ui/components/deepresearch/`

#### SetupPanel (`SetupPanel.tsx`)

The initial form where users configure their research task:
- **Research Description** (required) — textarea for the research question
- **Data Description** (optional) — textarea for data context
- **File Upload** — `FileUploadZone` component with drag-and-drop
- **Advanced Settings** — Collapsible section (model info, future per-stage config)
- **Submit** — Calls `createTask()` then navigates to Step 1

#### ReviewPanel (`ReviewPanel.tsx`)

Used for both Idea (Step 1) and Method (Step 2) review. Features:
- **Split layout:** 60% editor/preview + 40% refinement chat
- **Auto-execution:** If the stage is pending, it auto-triggers execution
- **Edit/Preview toggle:** Switch between raw markdown editing and rendered preview
- **Auto-save:** Debounced save (1 second) on content changes
- **Refinement Chat:** `RefinementChat` component for AI-assisted editing, with "Apply to editor" buttons
- **Failure handling:** Shows error with Retry button
- **Execution progress:** Shows `ExecutionProgress` while stage is running

#### ExecutionPanel (`ExecutionPanel.tsx`)

Used for Experiment Execution (Step 3):
- **Auto-execution:** Automatically starts when the stage is pending
- **Live console:** `ExecutionProgress` component showing real-time console output
- **Timer:** Elapsed time display
- **Cost display:** Running cost total
- **Retry on failure:** Shows error and Retry button

#### PaperPanel (`PaperPanel.tsx`)

Used for Paper Generation (Step 4):
- **Auto-execution:** Automatically starts paper generation
- **Execution progress:** Shows console output while generating
- **Success view:** Green banner with "Research Paper Complete" + download links for all artifacts
- **Cost summary:** Total cost and completed stages count
- **Download links:** Each artifact listed with file type icon and download button

#### RefinementChat (`RefinementChat.tsx`)

AI-powered chat sidebar for content editing:
- Chat-style interface (user messages right-aligned, assistant left-aligned)
- Each assistant message has an "Apply to editor" button
- Auto-scrolls to newest message
- Sends refinement requests to `POST /api/deepresearch/{task_id}/stages/{num}/refine`

#### FileUploadZone (`FileUploadZone.tsx`)

Drag-and-drop file upload UI:
- Drag-over visual feedback
- Click-to-browse option
- Status indicators per file: uploading (spinner), done (checkmark), error (alert)
- Supported formats: CSV, JSON, FITS, HDF5, TXT, MD, and more

#### ExecutionProgress (`ExecutionProgress.tsx`)

Console output display:
- Spinner + "Running {stageName}..." while executing
- Green "complete" indicator when done
- Monospace console output with auto-scroll
- Max height 400px with overflow scroll

---

## 12. File Upload & Data Handling

**Source:** `backend/routers/files.py`

### Upload Endpoint

`POST /api/files/upload`

Accepts multipart form data with:
- `file`: The file to upload
- `task_id`: The Deepresearch task ID
- `subfolder`: Target subfolder (typically `"input_files"`)

**Security measures:**
- Path traversal prevention (rejects `..` in paths)
- Extension whitelist: `.csv`, `.txt`, `.md`, `.json`, `.fits`, `.npy`, `.h5`, `.hdf5`, `.dat`, `.tsv`, `.xlsx`, `.xls`, `.png`, `.jpg`, `.jpeg`, `.pdf`
- Configurable file size limits
- Hidden file exclusion

### File Context Injection

When a stage executes, `_build_file_context()` scans `input_files/` for user-uploaded data files (excluding auto-generated files like `idea.md`, `methods.md`, etc.) and builds a context string appended to `data_description`:

```markdown
---
## Uploaded Data Files

The following data files have been uploaded and are available at the paths below.

### `galaxy_catalog.csv` (245.3KB)
**Absolute path:** `/path/to/input_files/galaxy_catalog.csv`

**Preview (first 15 lines):**
```
ra,dec,redshift,magnitude
123.456,45.678,0.5,21.3
...
```

Use the absolute paths above to read these files in your code.
```

This ensures LLM agents know about available data files and can reference them by absolute path in generated code.

---

## 13. Console Output & Real-Time Streaming

### Capture Mechanism

**Source:** `backend/routers/deepresearch.py:192-233`

The `_ConsoleCapture` class intercepts stdout/stderr during phase execution:

```python
class _ConsoleCapture:
    def write(self, text):
        # Write to original stream (for server logs)
        self._original.write(text)
        # Store in shared buffer (thread-safe)
        with _console_lock:
            _console_buffers[self._buf_key].append(text.rstrip())
```

Key design decisions:
- **Thread-safe:** Uses `threading.Lock` because phases run in thread pools via `asyncio.to_thread`
- **Dual output:** Writes to both original stdout and the buffer (logs appear in server terminal too)
- **Line-based:** Each non-empty write is stored as a separate line

### Delivery to Frontend

Two parallel channels deliver console output to the UI:

1. **REST polling** (primary for console lines):
   - `GET /api/deepresearch/{task_id}/stages/{num}/console?since=N`
   - Frontend polls every 2 seconds via `startConsolePoll()`
   - Uses `since` parameter for incremental fetching

2. **WebSocket** (primary for completion events):
   - `ws://host/ws/deepresearch/{task_id}/{stage_num}`
   - Sends `console_output` events every 1 second
   - Sends `stage_completed` / `stage_failed` when done
   - Flushes remaining buffer before closing

The frontend uses REST polling for console output to avoid duplication, and WebSocket primarily for completion notifications.

---

## 14. Task Resumption

**Source:** `mars-ui/hooks/useDeepresearchTask.ts:335-370`

Deepresearch tasks can be resumed after page reloads or interruptions:

1. `GET /api/deepresearch/recent` lists incomplete tasks
2. User selects a task to resume
3. `resumeTask(taskId)` is called, which:
   - Loads the full task state from `GET /api/deepresearch/{task_id}`
   - Determines the correct wizard step based on stage statuses:
     - If a stage is `"running"`: go to that step, reconnect WS + polls
     - If a stage is `"completed"`: advance past it
     - If a stage is `"pending"` or `"failed"`: stop at that step
   - Sets `currentStep` to the resume position

Stale `"running"` states (from a previous server session where the background task died) are detected in `execute_stage()` — if the stage shows `"running"` in the DB but the background task is no longer alive, the endpoint allows retry.

---

## 15. Cost Tracking & Observability

### Cost Tracking

Cost tracking for Stages 1-3 uses `CostCollector` (from `backend/execution/cost_collector.py`):

1. **Per-LLM-call tracking:** `CostCollector.collect_from_callback()` is invoked via the `on_cost_update` callback during execution
2. **Safety net:** `CostCollector.collect_from_work_dir()` scans the stage work directory post-execution for any cost logs that callbacks missed
3. **DB persistence:** Each cost entry is written to `CostRecord` via `CostRepository.record_cost()`
4. **Aggregation:** `GET /api/deepresearch/{task_id}` returns `total_cost_usd` aggregated across all stages

The frontend displays running costs in:
- The header bar of `DeepresearchResearchTask` (top-right)
- The stats bar in `ExecutionPanel` (timer + cost)
- The "Cost Summary" section in `PaperPanel` (final total)

### Execution Event Logging

Stages 1-3 log structured execution events via `EventRepository` (from `cmbagent/database/repository.py`):

| Event Type | Triggered By | Data |
|---|---|---|
| `agent_call` | `on_agent_message` callback | Agent name, message content |
| `code_exec` | `on_code_execution` callback | Code snippet, execution result |
| `tool_call` | `on_tool_call` callback | Tool name, arguments |

### Callback Architecture

The callback pipeline for Stages 1-3 is built using `WorkflowCallbacks` (from `cmbagent/callbacks.py`):

```python
# 1. Build event-tracking callbacks
workflow_callbacks = WorkflowCallbacks(
    on_agent_message=lambda msg: event_repo.create_event(type="agent_call", ...),
    on_code_execution=lambda code: event_repo.create_event(type="code_exec", ...),
    on_tool_call=lambda tool: event_repo.create_event(type="tool_call", ...),
    on_cost_update=lambda cost: cost_collector.collect_from_callback(cost),
)

# 2. Merge with print callbacks for structured logging
merged = merge_callbacks(create_print_callbacks(), workflow_callbacks)

# 3. Inject into kwargs
kwargs["callbacks"] = merged
```

This gives Deepresearch the same observability as the standard `task_executor.py` flow.

> **Note:** `DAGTracker` is intentionally skipped for Deepresearch — it requires a WebSocket in its
> constructor, and Deepresearch stages are linear (tracked by `TaskStage` rows rather than a DAG).

---

## 16. Testing

**Source:** `tests/`

### test_deepresearch_api.py

Tests the REST API layer:
- Task creation (standard vs deepresearch-research tasks)
- Task status retrieval with correct `task_type` and `mode`
- Stage listing (returns TaskStage objects with correct structure)
- Stage detail retrieval (output_data, output_files)
- 404 handling for non-existent stages

### test_deepresearch_phases.py

Unit tests for `stage_helpers` (pure functions) and `DeepresearchPaperPhase`:

**Stage helper tests (stages 1-3):**
- `TestBuildIdeaKwargs` — kwargs structure, default models, config overrides, work dir creation, parent_run_id
- `TestExtractIdeaResult` — extraction from chat_history, regex post-processing, missing agent error
- `TestSaveIdea` — file creation, directory setup
- `TestBuildIdeaOutput` — output dict structure
- `TestBuildMethodKwargs` — kwargs structure, prompt formatting with `{research_idea}`, default models
- `TestExtractMethodResult` — markdown extraction, code block stripping
- `TestSaveMethod` — file creation
- `TestBuildMethodOutput` — context preservation
- `TestBuildExperimentKwargs` — kwargs structure, prompt formatting with `{research_idea}` + `{methodology}` + `{involved_agents_str}`, default models
- `TestExtractExperimentResult` — results + plot path extraction
- `TestSaveExperiment` — results file + plots dir creation, plot file moving
- `TestBuildExperimentOutput` — full context preservation
- `TestDefaultModelConstants` — exact model assignments for all 3 stages

**DeepresearchPaperPhase (stage 4):**
- Calls `graph.ainvoke()` (async, not sync)
- Finds paper artifacts (prefers v4 > v3 > v2 > v1)
- Validates `input_files/` directory required
- Phase properties (`phase_type`, `display_name`)

**Config defaults:**
- Verifies `DeepresearchPaperPhaseConfig` default values (model, temperature, writer, etc.)

### test_deepresearch_integration.py

Integration tests for the full context flow using `stage_helpers` chained together:
- **`test_idea_to_method_to_experiment`:** 3-stage flow with mock PCC, verifying shared state accumulation and prompt injection
- **`test_files_created_across_stages`:** All `.md` files and `plots/` dir are created
- **`test_stage_work_dirs_created`:** Each stage creates its own work subdirectory (`idea_generation_output`, `method_generation_output`, `experiment_generation_output`)

---

## 17. Configuration & Model Defaults

### File Constants

**Source:** `cmbagent/task_framework/config.py`

```python
INPUT_FILES = "input_files"
PLOTS_FOLDER = "plots"
PAPER_FOLDER = "paper"
DESCRIPTION_FILE = "data_description.md"
IDEA_FILE = "idea.md"
METHOD_FILE = "methods.md"
RESULTS_FILE = "results.md"
LITERATURE_FILE = "literature.md"
REFEREE_FILE = "referee.md"
```

### Default Model Assignments

| Phase | Agent/Role | Model |
|---|---|---|
| **Idea** | idea_maker | `gpt-4o` |
| | idea_hater | `o3-mini` |
| | planner | `gpt-4o` |
| | plan_reviewer | `o3-mini` |
| | orchestration | `gpt-4.1` |
| | formatter | `o3-mini` |
| **Method** | researcher | `gpt-4.1` |
| | planner | `gpt-4.1` |
| | plan_reviewer | `o3-mini` |
| | orchestration | `gpt-4.1` |
| | formatter | `o3-mini` |
| **Experiment** | engineer | `gpt-4.1` |
| | researcher | `o3-mini` |
| | planner | `gpt-4o` |
| | plan_reviewer | `o3-mini` |
| | orchestration | `gpt-4.1` |
| | formatter | `o3-mini` |
| **Paper** | LLM (all nodes) | `gemini-2.5-flash` |

### Stage Definition Table

Defined in `STAGE_DEFS` (`routers/deepresearch.py`):

| Stage | Name | Execution Method | Shared Key | Output File |
|---|---|---|---|---|
| 1 | `idea_generation` | `_run_planning_control_stage()` | `research_idea` | `idea.md` |
| 2 | `method_development` | `_run_planning_control_stage()` | `methodology` | `methods.md` |
| 3 | `experiment_execution` | `_run_planning_control_stage()` | `results` | `results.md` |
| 4 | `paper_generation` | `_run_paper_stage()` | `None` | `None` |

> Stages 1-3 no longer have a `phase_type` key — they call `planning_and_control_context_carryover()`
> directly via `stage_helpers`. Only Stage 4 uses `DeepresearchPaperPhase`.

---

## 18. End-to-End User Flow

Here is the complete user journey through the Deepresearch workflow:

### Step 0: Setup

1. User navigates to the Tasks page and selects **"Research Paper"**
2. `DeepresearchResearchTask` mounts with `SetupPanel`
3. User enters:
   - **Research Description** (required): "Investigate the correlation between galaxy morphology and dark matter halo properties using SDSS data"
   - **Data Description** (optional): "SDSS DR16 galaxy catalog with photometric and spectroscopic measurements"
   - **File uploads** (optional): Drag-and-drop data files (`.csv`, `.fits`, etc.)
4. User clicks **"Generate Ideas"**
5. `createTask()` → `POST /api/deepresearch/create`
6. Backend creates:
   - Work directory: `cmbagent_workdir/deepresearch_tasks/{uuid}/input_files/`
   - Session with `mode="deepresearch-research"`
   - WorkflowRun + 4 TaskStage records (all `"pending"`)
   - Writes `data_description.md`
7. Frontend advances to Step 1

### Step 1: Idea Review

1. `ReviewPanel` mounts (stageNum=1, sharedKey="research_idea")
2. Stage is `"pending"` → auto-triggers `executeStage(1)`
3. `POST /api/deepresearch/{id}/stages/1/execute` → `_run_planning_control_stage()` background task
4. Backend:
   - Sets up `CostCollector` + `EventRepository` + `WorkflowCallbacks`
   - Calls `stage_helpers.build_idea_kwargs()` with data_description and work_dir
   - Calls `planning_and_control_context_carryover()` with full callbacks
   - idea_maker generates 5 ideas → idea_hater critiques → select best 2 → critique → select best 1
   - `stage_helpers.extract_idea_result()` extracts from `idea_maker_nest` agent, applies regex
   - `stage_helpers.save_idea()` writes to `input_files/idea.md`
   - `stage_helpers.build_idea_output()` builds `output_data` for DB
5. Frontend shows:
   - `ExecutionProgress` with live console output (via REST polling every 2s)
   - WebSocket listens for `stage_completed` event
6. On completion:
   - `fetchStageContent(1)` loads the generated idea into the editor
   - Split view: **Edit/Preview** (60%) + **Refinement Chat** (40%)
7. User reviews, optionally:
   - Edits the markdown directly (auto-saved after 1s debounce)
   - Uses Refinement Chat to ask AI to improve it (e.g., "Focus more on weak lensing")
   - Clicks "Apply to editor" on the refined version
8. User clicks **"Next"** → saves content → advances to Step 2

### Step 2: Method Review

1. `ReviewPanel` mounts (stageNum=2, sharedKey="methodology")
2. Same flow as Step 1, but:
   - `stage_helpers.build_method_kwargs()` receives `research_idea` from shared_state
   - Prompts are formatted with the (possibly user-edited) research idea via `{research_idea}`
   - Methodology is ~500 words, written as a senior researcher explaining to an assistant
   - `stage_helpers.save_method()` writes to `input_files/methods.md`
3. User reviews/edits the methodology, optionally uses Refinement Chat
4. User clicks **"Next"** → advances to Step 3

### Step 3: Experiment Execution

1. `ExecutionPanel` mounts (stageNum=3)
2. Auto-triggers `executeStage(3)`
3. `_run_planning_control_stage()`:
   - `stage_helpers.build_experiment_kwargs()` receives `research_idea` + `methodology`
   - Engineer writes and executes code (max 10 attempts, 500 control rounds)
   - Researcher writes ~2000-word results discussion
   - `stage_helpers.save_experiment()` moves plots to `input_files/plots/`, writes `input_files/results.md`
4. Frontend shows:
   - Live console output with elapsed timer and running cost
   - This is typically the longest stage
5. On completion/failure:
   - Success → "Next: Paper Generation" button enabled
   - Failure → error display + Retry button

### Step 4: Paper Generation

1. `PaperPanel` mounts (stageNum=4)
2. Auto-triggers `executeStage(4)`
3. `DeepresearchPaperPhase`:
   - `build_graph()` creates the LangGraph pipeline
   - `graph.ainvoke()` runs the paper generation:
     - `preprocess_node`: Initialize, load input files
     - `keywords_node` → `abstract_node` → `introduction_node` → `methods_node` → `results_node` → `conclusions_node`
     - `plots_node`: Process images, generate captions
     - `refine_results`: Improve results with figure references
     - `citation_router`: If `add_citations=True` → `citations_node` (uses Perplexity API)
   - Generates 4 paper versions (v1 → v4) as PDF + LaTeX
4. Frontend shows:
   - Execution progress while generating
   - On completion:
     - Green "Research Paper Complete" banner
     - Download links for each artifact (PDF, LaTeX files)
     - Cost summary (total cost + 4/4 stages completed)

### Task Complete

The user can download their generated research paper. The task remains in the database for future reference, and the complete work directory with all intermediate files is preserved.

---

## 19. Error Handling & Troubleshooting

### Overview

Deepresearch stages can fail for three broad reasons:

1. **LLM output failures** — The model returned an empty, malformed, or unparseable response
2. **Infrastructure failures** — Network timeouts, API rate limits, missing environment variables
3. **Data issues** — Required shared state is missing, uploaded files are unreadable, or paths don't exist

When a stage fails the UI shows the error message and a **Retry** button. The backend marks the `TaskStage` row as `"failed"` with the error text stored in `error_message`. Retrying re-runs the stage from scratch (no partial checkpointing within a stage).

---

### Stage 1 — Idea Generation

| Error | Cause | Fix |
|---|---|---|
| `Neither 'idea_maker_nest' nor 'idea_maker' found in chat history` | The idea generation agent didn't produce output | Retry; check `OPENAI_API_KEY` / model availability |
| Planner validation error | `plan_steps` is empty after planning (planner LLM returned `{"sub_tasks": []}`) | See [Planning Produces 0 Steps](#planning-produces-0-steps) |
| `Task is required for planning phase` | `data_description` was empty | Ensure a non-empty task description is provided at setup |

---

### Stage 2 — Method Development

| Error | Cause | Fix |
|---|---|---|
| `Plan is empty (0 steps)` | Planner produced `{"sub_tasks": []}` | See [Planning Produces 0 Steps](#planning-produces-0-steps) |
| `research_idea missing from shared state` | Stage 1 was not completed before Stage 2 was triggered | Complete Stage 1 first; the execute endpoint enforces ordering |
| Extraction fails (no researcher output) | Researcher agent produced no content | Retry; may be a model context-length or rate-limit issue |

---

### Stage 3 — Experiment Execution

| Error | Cause | Fix |
|---|---|---|
| `Plan is empty (0 steps)` | Planner produced `{"sub_tasks": []}` — the most common Stage 3 failure | See [Planning Produces 0 Steps](#planning-produces-0-steps) |
| `Plan is required for control phase (run planning first)` | Planning phase result was not carried into the control phase context | Internal state propagation bug; retry and inspect logs |
| Code execution timeout / sandbox error | The engineer's generated code ran too long or crashed | Retry; consider simplifying the methodology or adding `hardware_constraints` via `config_overrides` |
| `methodology missing from shared state` | Stage 2 was not completed | Complete Stage 2 first |
| `Neither 'researcher_response_formatter' nor 'researcher' found` | No researcher content generated | Retry; the control phase may have used all attempts on code fixes |

---

### Stage 4 — Paper Generation

| Error | Cause | Fix |
|---|---|---|
| `input_files/ directory does not exist` | Stages 1-3 were not completed | Run Stages 1-3 first |
| LaTeX compilation failure | Generated LaTeX has syntax errors | The system produces a `.tex` fallback even on PDF failure; download the `.tex` |
| `PERPLEXITY_API_KEY not set` | Citations requested but key missing | Set `PERPLEXITY_API_KEY` or pass `add_citations=False` in config |

---

### Planning Produces 0 Steps

**Symptom:** Stage fails with:
```
Planning produced 0 steps. The planner did not generate any plan steps — check the planner prompt, structured-output parsing, and model response.
```

**File:** `cmbagent/phases/planning.py`

**Root cause:**
The planner LLM's structured output (`PlannerResponse`) was parsed as `{"sub_tasks": []}`. This happens when:
- The model returns a valid JSON object with an empty `sub_tasks` list (the model decided no steps were needed, or its response was truncated)
- The `planner_response_formatter` agent ran but didn't produce valid structured output before the planning phase hit `max_rounds`

**Behaviour (post-fix, March 2026):**
The planning phase now **fails immediately** (returns `PhaseStatus.FAILED`) when `plan_steps_list` is empty, rather than completing with a 0-step plan and causing the less-informative downstream error:
```
# Old (confusing):
Phase control validation failed: ['Plan is required for control phase (run planning first)']

# New (clear):
Planning produced 0 steps. The planner did not generate any plan steps...
```

**Diagnosis steps:**

1. **Check `planning/final_plan.json`** in the stage's work directory:
   ```bash
   # Path pattern: {work_dir}/planning/final_plan.json
   # E.g.: cmbagent_workdir/deepresearch_tasks/{id}/experiment_generation_output/planning/final_plan.json
   cat planning/final_plan.json
   # If it shows {"sub_tasks": []}, the planner ran but produced no steps.
   ```

2. **Check the planner model** — if using a model with low context limits, the `plan_instructions` may be too long. Try a model with a larger context window via `config_overrides`.

3. **Check the `plan_instructions` prompt** — a very prescriptive or contradictory instruction set can cause the model to return an empty plan.

4. **Retry** — transient model failures resolve on retry in most cases.

**Source references:**
- Planning phase execution: [`cmbagent/phases/planning.py`](../cmbagent/phases/planning.py)
- Control phase validation: [`cmbagent/phases/control.py`](../cmbagent/phases/control.py)
- Planner structured output: [`cmbagent/agents/planner_response_formatter/planner_response_formatter.py`](../cmbagent/agents/planner_response_formatter/planner_response_formatter.py)

---

### Improving Error Visibility

All stage failures are:1. Stored in `TaskStage.error_message` (truncated to fit DB column)
2. Logged via `structlog` with full tracebacks at `ERROR` level
3. Sent over the WebSocket as a `stage_failed` event with `{ stage_num, error }` to the frontend
4. Displayed in the UI with the error message and a Retry button

For detailed diagnostics, inspect the stage's `error_message` via:
```bash
curl http://localhost:8000/api/deepresearch/{task_id}/stages/{stage_num}/content
```
or query the DB directly:
```sql
SELECT stage_number, status, error_message FROM task_stages
WHERE parent_run_id = '{task_id}' ORDER BY stage_number;
```
