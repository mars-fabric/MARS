# RFP Proposal Generator — End-to-End Integration Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Directory Structure](#3-directory-structure)
4. [The 7-Stage Pipeline](#4-the-7-stage-pipeline)
5. [Phase-Based Execution Engine](#5-phase-based-execution-engine)
6. [Shared State & Context Flow](#6-shared-state--context-flow)
7. [Backend API Reference](#7-backend-api-reference)
8. [Database Layer](#8-database-layer)
9. [Phase Classes & Prompts](#9-phase-classes--prompts)
10. [Frontend UI](#10-frontend-ui)
11. [File Upload & PDF Extraction](#11-file-upload--pdf-extraction)
12. [Console Output & Real-Time Streaming](#12-console-output--real-time-streaming)
13. [Task Resumption](#13-task-resumption)
14. [Cost Tracking](#14-cost-tracking)
15. [Configuration & Model Defaults](#15-configuration--model-defaults)
16. [Token Capacity Management](#16-token-capacity-management)
17. [Dynamic Currency System](#17-dynamic-currency-system)
18. [Divide-and-Accumulate Strategy (Stage 7)](#18-divide-and-accumulate-strategy-stage-7)
19. [Refinement Chat Token Safety](#19-refinement-chat-token-safety)
20. [End-to-End User Flow](#20-end-to-end-user-flow)
21. [Error Handling](#21-error-handling)
22. [Multi-Agent System](#22-multi-agent-system)

---

## 1. Overview

The RFP Proposal Generator is a **7-stage, human-in-the-loop AI workflow** in MARS. It transforms an RFP document into a complete technical proposal through interactive stages:

1. **Requirements Analysis** → 2. **Tools & Technology** → 3. **Cloud & Infrastructure** → 4. **Implementation Plan** → 5. **Architecture Design** → 6. **Execution Strategy** → 7. **Proposal Compilation**

Each stage uses a dedicated **Phase class** (`cmbagent/phases/rfp/`) with a **3-agent pipeline** (Primary → Specialist → Reviewer: 3 LLM calls per stage when `multi_agent=True`, the default). Users can review, edit, and refine AI output between every stage.

**Key technologies:**
- **Backend:** Python, FastAPI, SQLAlchemy, asyncio
- **Phase System:** `RfpPhaseBase` → 7 phase subclasses with 3-agent pipeline (primary → specialist → reviewer)
- **Frontend:** React, TypeScript, Next.js
- **Real-time:** WebSocket + REST polling
- **Default LLM:** Dynamic from `WorkflowConfig.default_llm_model` (configurable per stage via `config_overrides`)
- **Mode:** `"rfp-proposal"`

---

## 2. Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React/Next.js)                      │
│                                                                       │
│  TaskList.tsx ──► RfpProposalTask.tsx (8-step wizard)                 │
│                    ├── RfpSetupPanel.tsx       (Step 0)               │
│                    ├── RfpReviewPanel.tsx      (Steps 1–6)            │
│                    ├── RfpExecutionPanel.tsx   (per-stage monitoring) │
│                    └── RfpProposalPanel.tsx    (Step 7)               │
│                                                                       │
│  useRfpTask.ts ── state management, API calls, WebSocket             │
└───────────┬──────────────────────────────┬────────────────────────────┘
            │ REST API                     │ WebSocket
            ▼                              ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                              │
│                                                                       │
│  routers/rfp.py ── REST endpoints + phase-based execution engine     │
│    _run_rfp_stage():                                                  │
│      1. _load_phase_class(stage_num)  ── dynamic importlib load      │
│      2. PhaseClass(config=...)        ── instantiate phase            │
│      3. PhaseContext(task, work_dir, shared_state)                    │
│      4. await phase.execute(ctx)      ── generate → review cycle     │
│      5. Extract output, track cost, update DB                        │
│                                                                       │
│  main.py          ── WebSocket /ws/rfp/{task_id}/{stage_num}         │
│  services/pdf_extractor.py ── rich PDF extraction (text+tables+images)│
└───────────┬──────────────────────────────┬────────────────────────────┘
            │                              │
            ▼                              ▼
┌────────────────────────┐    ┌─────────────────────────────────────────┐
│     DATABASE (SQLite)  │    │   PHASE CLASSES (cmbagent/phases/rfp/)  │
│                        │    │                                         │
│  WorkflowRun           │    │  base.py ── RfpPhaseBase                │
│  TaskStage (×7)        │    │    ├── system_prompt (property)         │
│  Session               │    │    ├── review_system_prompt (property)  │
│  CostRecord            │    │    ├── build_user_prompt(ctx) (method)  │
│                        │    │    └── execute(ctx) → PhaseResult       │
│  TaskStageRepository   │    │        ├── Generation pass (1 LLM call) │
│  CostRepository        │    │        └── Review pass(es) (n LLM calls)│
└────────────────────────┘    └─────────────────────────────────────────┘
```

---

## 3. Directory Structure

```
backend/
├── main.py                    # FastAPI app + WS endpoints (/ws/rfp/{task_id}/{stage_num})
├── models/
│   └── rfp_schemas.py         # Pydantic request/response schemas
├── routers/
│   ├── __init__.py            # Router registration
│   ├── rfp.py                 # RFP REST API + execution engine (~950 lines)
│   └── files.py               # File upload/download endpoint
├── services/
│   ├── pdf_extractor.py       # Rich PDF extraction (text, tables, images)
│   └── session_manager.py     # Session lifecycle

cmbagent/phases/rfp/
├── __init__.py                # Imports all phase classes
├── base.py                    # RfpPhaseBase — generate→review cycle engine
├── requirements_phase.py      # Stage 1: RfpRequirementsPhase
├── tools_phase.py             # Stage 2: RfpToolsPhase
├── cloud_phase.py             # Stage 3: RfpCloudPhase
├── implementation_phase.py    # Stage 4: RfpImplementationPhase
├── architecture_phase.py      # Stage 5: RfpArchitecturePhase
├── execution_phase.py         # Stage 6: RfpExecutionPhase
└── proposal_phase.py          # Stage 7: RfpProposalPhase

mars-ui/
├── app/tasks/page.tsx         # Task routing ("rfp-proposal" → RfpProposalTask)
├── types/rfp.ts               # TypeScript types and constants
├── hooks/useRfpTask.ts        # React hook for all RFP state management
└── components/
    ├── tasks/
    │   ├── TaskList.tsx        # Task catalog (lists "RFP Proposal Generator")
    │   └── RfpProposalTask.tsx # Main 8-step wizard container
    └── rfp/
        ├── RfpSetupPanel.tsx   # Step 0: RFP content + file upload
        ├── RfpReviewPanel.tsx  # Steps 1–6: edit/preview + refinement chat
        ├── RfpExecutionPanel.tsx # Per-stage execution monitoring
        └── RfpProposalPanel.tsx # Step 7: final proposal + downloads

cmbagent_workdir/sessions/{session_id}/tasks/{task_id}/input_files/
├── rfp_input.md               # Original RFP text
├── rfp_context.md             # Additional context (optional)
├── requirements.md            # Stage 1 output
├── tools.md                   # Stage 2 output
├── cloud.md                   # Stage 3 output
├── implementation.md          # Stage 4 output
├── architecture.md            # Stage 5 output
├── execution.md               # Stage 6 output
├── proposal.md                # Stage 7 output (final proposal)
└── [user-uploaded files]      # PDFs, DOCX, etc.
```

---

## 4. The 7-Stage Pipeline

### Stage 1 — Requirements Analysis

**Phase class:** `RfpRequirementsPhase` in `cmbagent/phases/rfp/requirements_phase.py`

**What it extracts:**
1. Functional Requirements
2. Non-Functional Requirements (performance, security, scalability, compliance)
3. Stakeholders
4. Constraints (budget, timeline, technology, regulatory)
5. Success Criteria
6. Risk Factors and mitigation strategies
7. Assumptions
8. Deliverables
9. Budget Analysis (critical for downstream cost-aware stages)
10. **Currency** — Identifies the currency used in the RFP (USD, EUR, GBP, INR, etc.) by scanning for currency symbols, codes, or country context. Outputs `## Currency` section with `**Primary Currency:** <CODE> (<SYMBOL>)`. Defaults to USD ($) if not found. This currency is used by all downstream stages (see [Section 17](#17-dynamic-currency-system)).

**Input:** `rfp_content` (user's RFP text) + `rfp_context` (optional) + uploaded file content
**Output:** `shared_state.requirements_analysis` → `requirements.md`

### Stage 2 — Tools & Technology Selection

**Phase class:** `RfpToolsPhase` in `cmbagent/phases/rfp/tools_phase.py`

**What it produces:**
- Head-to-head **comparison table** per tool category (Recommended vs Alternatives)
- **Security assessment** per tool (CVE history, compliance certs, encryption)
- Cost estimates (Monthly + Annual, in the RFP's detected currency)
- Security Summary Matrix across all tools
- Total Tool Cost Summary
- Cost Optimization Recommendations

**Input:** `requirements_analysis` from Stage 1
**Output:** `shared_state.tools_technology` → `tools.md`

### Stage 3 — Cloud & Infrastructure Planning

**Phase class:** `RfpCloudPhase` in `cmbagent/phases/rfp/cloud_phase.py`

**What it produces:**
- Cloud Provider Comparison Matrix (AWS vs Azure vs GCP)
- Selected provider justification with data-backed reasons
- Why other providers were NOT selected
- Compute, storage, networking, security architecture
- Managed Services Comparison across providers
- Detailed cost breakdown (Monthly + Annual, USD only)
- Cost optimization strategy

**Input:** `requirements_analysis` + `tools_technology`
**Output:** `shared_state.cloud_infrastructure` → `cloud.md`

### Stage 4 — Implementation Plan

**Phase class:** `RfpImplementationPhase` in `cmbagent/phases/rfp/implementation_phase.py`

**What it produces:** Project phases, timeline, sprint planning, team composition, resource allocation, dependencies, risk mitigation, quality gates, communication plan, budget breakdown.

**Input:** `requirements_analysis` + `tools_technology` + `cloud_infrastructure`
**Output:** `shared_state.implementation_plan` → `implementation.md`

### Stage 5 — Architecture Design

**Phase class:** `RfpArchitecturePhase` in `cmbagent/phases/rfp/architecture_phase.py`

**What it produces:** High-level architecture, component design, data architecture, integration patterns, security architecture, deployment architecture, scalability design, monitoring & observability, ADRs.

**Input:** All 4 prior shared_state keys
**Output:** `shared_state.architecture_design` → `architecture.md`

### Stage 6 — Execution Strategy

**Phase class:** `RfpExecutionPhase` in `cmbagent/phases/rfp/execution_phase.py`

**What it produces:** Kickoff & onboarding, dev methodology, environment strategy, testing strategy, CI/CD, release management, go-live plan, post-launch support, knowledge transfer, KPIs, governance.

**Input:** All 5 prior shared_state keys
**Output:** `shared_state.execution_strategy` → `execution.md`

### Stage 7 — Proposal Compilation

**Phase class:** `RfpProposalPhase` in `cmbagent/phases/rfp/proposal_phase.py`

**What it produces:** Complete professional proposal document:
- Cover Page, Executive Summary, Understanding of Requirements
- Proposed Solution, Technology Stack, Cloud Infrastructure
- System Architecture, Implementation Approach, Execution Plan
- Risk Management, Pricing Summary & TCO, Team & Qualifications
- Terms & Assumptions
- **Appendices:** Detailed cost breakdowns, technology evaluation matrices, glossary (20-30+ entries), references (10-15+ citations)

**Execution Strategy:** Uses a **divide-and-accumulate** approach for zero data loss (see [Section 18](#18-divide-and-accumulate-strategy-stage-7)):
- **PATH A:** If all 6 sources fit the context window → single generation call
- **PATH A → B fallback:** If PATH A returns empty/short output (tiktoken undercount) → automatically falls back to PATH B
- **PATH B:** Divide sources into groups via `group_sources_by_budget()` → generate partial proposals per group → accumulation pass to merge

**Input:** All 6 prior shared_state keys
**Output:** `proposal.md` (final compiled proposal)

---

## 5. Phase-Based Execution Engine

### Phase Class Hierarchy

```
Phase (cmbagent/phases/base.py)             # Abstract base
  └── RfpPhaseBase (cmbagent/phases/rfp/base.py)  # Generate→review engine
        ├── RfpRequirementsPhase             # Stage 1
        ├── RfpToolsPhase                    # Stage 2
        ├── RfpCloudPhase                    # Stage 3
        ├── RfpImplementationPhase           # Stage 4
        ├── RfpArchitecturePhase             # Stage 5
        ├── RfpExecutionPhase                # Stage 6
        └── RfpProposalPhase                 # Stage 7
```

### RfpPhaseBase — Core Execution

Each phase subclass provides:
- `phase_type` — Registry identifier (e.g., `"rfp_requirements"`)
- `display_name` — Human-readable name
- `shared_output_key` — Output key in shared_state dict
- `output_filename` — File to save output to
- `system_prompt` — Expert persona for generation pass
- `review_system_prompt` — Reviewer persona for review pass (inherited from base)
- `build_user_prompt(context)` — Constructs the prompt from shared_state

### Generate → Review Cycle

```
RfpPhaseBase.execute(context)
  │
  ├── 1. Build user prompt via self.build_user_prompt(context)
  │
  ├── 2. Generation pass (1 LLM call):
  │     system = self.system_prompt
  │     user   = self.build_user_prompt(context)
  │     → content (draft)
  │
  ├── 3. Review pass(es) (n_reviews × 1 LLM call each):
  │     system = self.review_system_prompt
  │     user   = "Draft document:\n\n{content}"
  │     → content (improved)
  │
  ├── 4. Save to disk: {work_dir}/input_files/{output_filename}
  │
  └── 5. Return PhaseResult with:
        output_data = {
          "shared": { shared_output_key: content },
          "artifacts": { "model": model },
          "cost": { "prompt_tokens": X, "completion_tokens": Y }
        }
```

**Default config:** model=dynamic from `WorkflowConfig`, temperature=`0.7`, max_completion_tokens=`16384`, n_reviews=`1`, multi_agent=`True`

With `multi_agent=True` and `n_reviews=1`, each stage makes **3 LLM calls** (1 primary + 1 specialist + 1 review). Total for 7 stages: **21 LLM calls**. Set `multi_agent=False` for the original 2-call generate→review cycle (14 calls).

**Token capacity:** Before each LLM call, token count is checked against the model's max context window. If the prompt exceeds capacity, it is automatically split at section boundaries into multiple sub-requests (see [Section 16: Token Capacity Management](#16-token-capacity-management)).

### Review System Prompt

The shared review prompt (in `RfpPhaseBase`) enforces a **13-point quality checklist**:
1. Fix factual errors, strengthen weak sections, add missing detail
2. Improve structure and flow, ensure proper section numbering
3. Ensure ALL cost figures are present, consistent, and fit within budget
4. Verify every tool/technology has a comparison table vs alternatives
5. Verify security comparisons for each major tool and service
6. Verify cloud provider comparison and justification are thorough
7. Add professional tables where data is listed as bullets
8. Replace ALL placeholder text (`[Insert ...]`, `[To be added]`) with ACTUAL content
9. Ensure ALL monetary values use a **single consistent currency** throughout — no mixed currencies (currency is determined dynamically from the RFP; see [Section 17](#17-dynamic-currency-system))
10. Verify every cost table has Monthly and Annual columns with actual figures
11. Verify Annual Cost = Monthly Cost × 12 (fix math errors)
12. Verify appendices contain REAL content (full tables, glossary, references)
13. Polish to enterprise-quality prose

### Dynamic Phase Loading

The router loads phases dynamically via `importlib` to avoid circular imports:

```python
_PHASE_CLASSES = {
    1: "cmbagent.phases.rfp.requirements_phase:RfpRequirementsPhase",
    2: "cmbagent.phases.rfp.tools_phase:RfpToolsPhase",
    # ... stages 3-7
}

def _load_phase_class(stage_num):
    import importlib
    ref = _PHASE_CLASSES[stage_num]
    module_path, cls_name = ref.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)
```

### Stage Execution Flow (`_run_rfp_stage`)

```python
async def _run_rfp_stage(task_id, stage_num, work_dir, rfp_content,
                          rfp_context, shared_state, config_overrides, session_id):
    # 1. Set up console capture (stdout → WebSocket buffer)
    sys.stdout = _ConsoleCapture(buf_key, old_stdout)

    # 2. Load and instantiate Phase class
    PhaseClass = _load_phase_class(stage_num)
    phase = PhaseClass(config=PhaseClass.config_class(model=model, n_reviews=n_reviews))

    # 3. Build PhaseContext with accumulated shared_state
    ctx = PhaseContext(
        workflow_id=f"rfp_{task_id}",
        task=rfp_content,
        work_dir=work_dir,
        shared_state={**shared_state, "rfp_context": rfp_context},
    )

    # 4. Execute phase (generate → review cycle)
    result = await phase.execute(ctx)

    # 5. Extract content from result
    content = result.context.output_data["shared"][shared_key]

    # 6. Track cost
    cost_repo.record_cost(parent_run_id=task_id, model=model, ...)

    # 7. Save to file + update DB stage status
    repo.update_stage_status(stage.id, status="completed", output_data=output_data)
```

---

## 6. Shared State & Context Flow

Each stage reads from all prior stages and writes its own output:

```
Stage 1 → { requirements_analysis }
Stage 2 → { requirements_analysis, tools_technology }
Stage 3 → { requirements_analysis, tools_technology, cloud_infrastructure }
Stage 4 → { ..., implementation_plan }
Stage 5 → { ..., architecture_design }
Stage 6 → { ..., execution_strategy }
Stage 7 → reads all 6 keys → writes proposal.md
```

**Reconstruction:** `build_shared_state()` queries all completed `TaskStage` records and merges their `output_data["shared"]` dicts:

```python
def build_shared_state(task_id, up_to_stage, db, session_id="rfp"):
    repo = _get_stage_repo(db, session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared
```

**Human edits flow forward:** When a user edits a stage's content, both the DB and filesystem are updated. The next stage reads the edited version.

---

## 7. Backend API Reference

All endpoints are prefixed with `/api/rfp/`. Source: `backend/routers/rfp.py`.

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/rfp/create` | Create new task with 7 pending stages |
| PATCH | `/{task_id}/description` | Update RFP text/context (for auto-created tasks) |
| GET | `/api/rfp/recent` | List incomplete tasks for resume flow |
| GET | `/{task_id}` | Full task state (stages, progress %, cost) |
| POST | `/{task_id}/stages/{N}/execute` | Execute stage in background |
| GET | `/{task_id}/stages/{N}/content` | Get stage output content |
| PUT | `/{task_id}/stages/{N}/content` | Save user edits |
| POST | `/{task_id}/stages/{N}/refine` | LLM refinement of content |
| GET | `/{task_id}/stages/{N}/console` | Console output (polling) |
| POST | `/{task_id}/reset-from/{N}` | Reset stage N+ back to pending |
| GET | `/{task_id}/download/{filename}` | Download artifact file |
| DELETE | `/{task_id}` | Delete task + work directory |

### WebSocket Endpoint

**URL:** `ws://host/ws/rfp/{task_id}/{stage_num}`

| Event | When |
|-------|------|
| `status` | On connection |
| `console_output` | Every 1s with new console lines |
| `stage_completed` | Stage finished successfully |
| `stage_failed` | Stage failed with error |

### Pydantic Schemas (`backend/models/rfp_schemas.py`)

| Schema | Type | Fields |
|--------|------|--------|
| `RfpCreateRequest` | Request | `task`, `rfp_context?`, `config?`, `work_dir?` |
| `RfpExecuteRequest` | Request | `config_overrides?` |
| `RfpContentUpdateRequest` | Request | `content`, `field` |
| `RfpRefineRequest` | Request | `message`, `content` |
| `RfpCreateResponse` | Response | `task_id`, `work_dir`, `stages[]` |
| `RfpStageContentResponse` | Response | `stage_number`, `status`, `content`, `shared_state` |
| `RfpRefineResponse` | Response | `refined_content`, `message` |
| `RfpTaskStateResponse` | Response | Full task state with stages, progress, cost |
| `RfpRecentTaskResponse` | Response | Summary for resume flow |

---

## 8. Database Layer

Source: `cmbagent/database/models.py`, `cmbagent/database/repository.py`

### Models

**WorkflowRun** — Parent record for an RFP task:

| Column | RFP Usage |
|--------|-----------|
| `id` | Task UUID |
| `session_id` | FK → Session |
| `mode` | `"rfp-proposal"` |
| `agent` | `"phase_orchestrator"` |
| `model` | Dynamic from `WorkflowConfig` |
| `status` | `"executing"` → `"completed"` / `"failed"` |
| `task_description` | User's RFP text |
| `meta` | `{ work_dir, rfp_context, config, session_id, orchestration: "phase-based" }` |

**TaskStage** — Individual stage tracking (7 per task):

| Column | Description |
|--------|-------------|
| `id` | UUID primary key |
| `parent_run_id` | FK → WorkflowRun.id |
| `stage_number` | 1–7 |
| `stage_name` | `requirements_analysis`, `tools_technology`, etc. |
| `status` | `pending` → `running` → `completed` / `failed` |
| `output_data` | `{ shared: { key: content }, artifacts: { model }, cost: { tokens } }` |
| `output_files` | List of generated file names |
| `error_message` | Error text if failed |

**CostRecord** — Per-LLM-call cost tracking:

| Column | Description |
|--------|-------------|
| `parent_run_id` | FK → WorkflowRun.id |
| `model` | Model used (from `WorkflowConfig` or `config_overrides`) |
| `prompt_tokens` | Input tokens |
| `completion_tokens` | Output tokens |
| `cost_usd` | Calculated cost |

### Repositories

**TaskStageRepository:** `create_stage()`, `list_stages()`, `update_stage_status()`, `get_task_progress()`
**CostRepository:** `record_cost()`, `get_task_total_cost()`, `get_session_cost()`

---

## 9. Phase Classes & Prompts

Source: `cmbagent/phases/rfp/`

### Phase Properties

| Stage | Phase Class | phase_type | shared_output_key | output_filename | System Prompt Persona | Specialist Role |
|-------|-------------|------------|-------------------|-----------------|-----------------------|-----------------|
| 1 | `RfpRequirementsPhase` | `rfp_requirements` | `requirements_analysis` | `requirements.md` | Expert Business Analyst (15+ years) | Domain Validation Expert |
| 2 | `RfpToolsPhase` | `rfp_tools` | `tools_technology` | `tools.md` | Senior Solutions Architect & Technology Evaluator (20+ years) | Security & Compliance Auditor |
| 3 | `RfpCloudPhase` | `rfp_cloud` | `cloud_infrastructure` | `cloud.md` | Cloud Infrastructure Architect (20+ years, AWS/Azure/GCP) | Cloud Cost Optimisation Specialist |
| 4 | `RfpImplementationPhase` | `rfp_implementation` | `implementation_plan` | `implementation.md` | Senior Project Manager & Delivery Lead | Delivery Assurance Analyst |
| 5 | `RfpArchitecturePhase` | `rfp_architecture` | `architecture_design` | `architecture.md` | Principal System Architect | Scalability & Implementation Engineer |
| 6 | `RfpExecutionPhase` | `rfp_execution` | `execution_strategy` | `execution.md` | Delivery Executive & Program Manager | Risk & Governance Specialist |
| 7 | `RfpProposalPhase` | `rfp_proposal` | `proposal_compilation` | `proposal.md` | World-Class Proposal Writer (Fortune 500, $10M–$500M) | Senior Proposal Editor |

Each phase defines three key prompts: `system_prompt` (primary agent persona), `specialist_system_prompt` (domain validation agent), and the shared `review_system_prompt` (13-point quality checklist).

### Prompt Quality Rules (enforced across phases)

- **Dynamic currency** — All costs must use the currency detected from the RFP (defaults to USD if not found) — no mixed currencies
- **Cost table format** — Both Monthly and Annual columns, Annual = Monthly × 12, no empty cells
- **No placeholders** — Zero bracket-enclosed placeholder text (`[Insert ...]` forbidden)
- **Comparison tables** — Every tool/technology must have head-to-head comparison vs alternatives
- **Security assessment** — CVE history, compliance certs, encryption features per tool
- **Budget awareness** — All recommendations must fit within the RFP's stated budget

---

## 10. Frontend UI

### Type Definitions (`mars-ui/types/rfp.ts`)

Key types: `RfpTaskState`, `RfpStage`, `RfpWizardStep` (0–7), `RfpStageConfig`

Constants: `RFP_STEP_LABELS`, `RFP_WIZARD_STEP_TO_STAGE`, `RFP_STAGE_SHARED_KEYS`, `RFP_STAGE_NAMES`, `RFP_AVAILABLE_MODELS` (9 models)

### State Management Hook (`mars-ui/hooks/useRfpTask.ts`)

`useRfpTask()` provides: `taskId`, `taskState`, `currentStep`, `isExecuting`, `editableContent`, `consoleOutput`, `uploadedFiles`, `lastExtractedText`

Actions: `createTask()`, `executeStage()`, `fetchStageContent()`, `saveStageContent()`, `refineContent()`, `uploadFile()`, `resumeTask()`, `deleteTask()`, `resetFromStage()`

### Wizard Container (`mars-ui/components/tasks/RfpProposalTask.tsx`)

8-step wizard with `Stepper` navigation:

| Step | Component | Stage |
|------|-----------|-------|
| 0 | `RfpSetupPanel` | (no stage) |
| 1–6 | `RfpReviewPanel` | Stages 1–6 |
| 7 | `RfpProposalPanel` | Stage 7 |

### Panel Components

- **RfpSetupPanel** — File upload (above textarea), RFP content textarea (auto-populated from PDF), additional context, "Analyze Requirements" button
- **RfpReviewPanel** — 60% editor/preview + 40% refinement chat, auto-save (1s debounce), stage execution monitoring
- **RfpProposalPanel** — Success banner, proposal preview, download links for all 7 artifacts

---

## 11. File Upload & PDF Extraction

### Upload Flow

`POST /api/files/upload` → saves file to `input_files/` → extracts text from PDFs → returns `extracted_text` in response

### Rich PDF Extraction (`backend/services/pdf_extractor.py`)

Uses PyMuPDF (fitz) to extract:
- **Text** — Block-level extraction with table region deduplication
- **Tables** — `page.find_tables()` → markdown table format
- **Images** — Dimensions, format descriptions
- Output cap: 500KB

### File Context Injection

`_build_rfp_context()` scans uploaded files (excluding auto-generated .md files) and builds a context string appended to `rfp_context` before each stage execution.

---

## 12. Console Output & Real-Time Streaming

### Capture

`_ConsoleCapture` intercepts stdout/stderr during stage execution → thread-safe buffer keyed by `{task_id}:{stage_num}`

### Delivery

1. **REST polling** — `GET /api/rfp/{task_id}/stages/{N}/console?since=X` every 2 seconds
2. **WebSocket** — `ws://host/ws/rfp/{task_id}/{N}` sends `console_output` events every 1 second, `stage_completed`/`stage_failed` on finish

---

## 13. Task Resumption

`GET /api/rfp/recent` → lists incomplete tasks → user selects → `resumeTask(taskId)` loads full state and sets wizard position based on stage statuses (running → reconnect WS, completed → advance, pending/failed → stop).

---

## 14. Cost Tracking

Each LLM call's token usage is recorded via `CostRepository`:
- Input tokens × $0.002/1K + output tokens × $0.008/1K (GPT-4.1 pricing)
- Per-stage cost stored in `output_data["cost"]`
- Total cost exposed via `GET /api/rfp/{task_id}` → `total_cost_usd`
- Displayed in header bar, execution panel, and proposal success banner

---

## 15. Configuration & Model Defaults

### Stage Definitions (`STAGE_DEFS`)

| Stage | Name | Shared Key | Output File |
|-------|------|------------|-------------|
| 1 | `requirements_analysis` | `requirements_analysis` | `requirements.md` |
| 2 | `tools_technology` | `tools_technology` | `tools.md` |
| 3 | `cloud_infrastructure` | `cloud_infrastructure` | `cloud.md` |
| 4 | `implementation_plan` | `implementation_plan` | `implementation.md` |
| 5 | `architecture_design` | `architecture_design` | `architecture.md` |
| 6 | `execution_strategy` | `execution_strategy` | `execution.md` |
| 7 | `proposal_compilation` | `proposal_compilation` | `proposal.md` |

### Phase Config Defaults (`RfpPhaseConfig`)

| Parameter | Default | Notes |
|-----------|---------|-------|
| `model` | Dynamic (`_default_model()`) | Resolved from `WorkflowConfig.default_llm_model` at runtime; overridable via `config_overrides` |
| `temperature` | `0.7` | Balanced creativity/consistency (omitted for reasoning models like o3-mini) |
| `max_completion_tokens` | `16384` | Sufficient for detailed markdown |
| `n_reviews` | `1` | 1 review pass per stage |
| `review_model` | `None` (same as model) | Can use a different model for review |
| `multi_agent` | `True` | Enable 3-agent pipeline (primary → specialist → reviewer). Set `False` for 2-pass generate→review. |
| `specialist_model` | `None` (per-stage) | Override specialist model; defaults from `get_phase_models()` in `agent_teams.py` |

### Stage-to-Model Map (Dynamic)

All stages resolve their model dynamically from `WorkflowConfig.default_llm_model` — **no model names are hardcoded**.

The resolution chain:
1. `_get_default_rfp_model()` in `backend/routers/rfp.py` reads from `WorkflowConfig`
2. `_default_model()` in `base.py` reads from `WorkflowConfig` (used by `RfpPhaseConfig.model`)
3. `_cfg_model()` in `agent_teams.py` reads from `WorkflowConfig` (used by `get_phase_models()`)
4. `_default_model()` in `token_utils.py` reads from `WorkflowConfig` (used by `count_tokens()` default)

All 7 stages × all 3 agents (primary, specialist, reviewer) use the **same configured model**.

Users can override per-stage via `config_overrides` in the execute request.

> **Azure deployment:** Ensure `AZURE_OPENAI_DEPLOYMENT` is set to your deployment name.
> Set `CMBAGENT_DEFAULT_MODEL` environment variable or update `WorkflowConfig` to change the model for all stages.

### Available Models (10)

GPT-5.3, GPT-4.1, GPT-4.1 Mini, GPT-4o, GPT-4o Mini, o3-mini, Gemini 2.5 Pro, Gemini 2.5 Flash, Claude Sonnet 4, Claude 3.5 Sonnet

---

## 16. Token Capacity Management

Source: `cmbagent/phases/rfp/token_utils.py`, integrated in `cmbagent/phases/rfp/base.py`, `cmbagent/phases/rfp/proposal_phase.py`, and `backend/routers/rfp.py`

### Problem

Later stages (especially Stage 7 — Proposal Compilation) inject all prior stage outputs into the prompt. For models with smaller context windows (e.g., GPT-4o at 128K tokens), the combined prompt can exceed the model's capacity and cause API errors or truncated output (`finish_reason=length`).

### Solution: Comprehensive Token Protection at Every LLM Call

**All 11 LLM call sites** (with `multi_agent=True`) in the RFP pipeline are protected with token capacity management:

| # | Call Site | File | Protection |
|---|-----------|------|------------|
| 1 | Generation pass (single-shot) | `base.py` | `chunk_prompt_if_needed` + dynamic `max_completion_tokens` cap |
| 2 | Generation pass (chunked) | `base.py` | Per-chunk dynamic `max_completion_tokens` cap |
| 3 | Specialist pass (single-shot) | `base.py` | `chunk_prompt_if_needed` + dynamic `max_completion_tokens` cap |
| 4 | Specialist pass (chunked) | `base.py` | Per-chunk dynamic `max_completion_tokens` cap |
| 5 | Review pass (single-shot) | `base.py` | `chunk_prompt_if_needed` + dynamic `max_completion_tokens` cap |
| 6 | Review pass (chunked) | `base.py` | Per-chunk dynamic `max_completion_tokens` cap |
| 7 | Stage 7 `_single_generate` | `proposal_phase.py` | Dynamic `max_completion_tokens` cap via `get_model_limits` |
| 8 | Stage 7 specialist | `proposal_phase.py` | `_run_specialist()` (inherited) |
| 9 | Stage 7 review (single-shot) | `proposal_phase.py` | `chunk_prompt_if_needed` + dynamic cap |
| 10 | Stage 7 review (chunked) | `proposal_phase.py` | Per-chunk dynamic cap |
| 11 | Refinement chat | `rfp.py` | Dynamic cap + content trimming when overflow |

### Safety Margin: 0.75 (75%)

All token budget calculations use a **0.75 safety margin** instead of the theoretical maximum. This is because `tiktoken` (the token counting library) can undercount by 10–20% compared to the API's actual tokenizer due to special tokens, markdown formatting, and Unicode handling.

```python
usable_ctx = int(max_ctx * 0.75) - max_completion_tokens
```

### Dynamic `max_completion_tokens` Capping

At every LLM call, the `max_completion_tokens` parameter is dynamically capped so that `prompt_tokens + max_completion_tokens` never exceeds the model's context window:

```python
prompt_tokens = count_tokens(system + user, model)
available_for_output = max_ctx - prompt_tokens - 200  # 200 token safety buffer
max_comp = min(config.max_completion_tokens, max(available_for_output, 4096))
```

This prevents `finish_reason=length` truncation and ensures the model has room for both prompt and output.

### Prompt Chunking Strategy

When the full prompt exceeds the usable context window, it is automatically split:

```
RfpPhaseBase.execute(context)
  │
  ├── 1. Count tokens: system_prompt + user_prompt
  │
  ├── 2. Compare against: (max_context × 0.75) - max_completion_tokens
  │
  ├── 3a. If fits → single API call with dynamic max_completion_tokens cap
  │
  └── 3b. If exceeds → split user_prompt at '---' section boundaries
          ├── Chunk 1: sections 1..N  → API call (dynamic cap) → partial output 1
          ├── Chunk 2: sections N+1..M → API call (dynamic cap) → partial output 2
          └── Combine: partial output 1 + partial output 2 = full content
```

The same chunking logic applies to **review passes** — if the draft document is too large for the review model's context, the review is split into sub-reviews that are independently capped and then concatenated.

### Overflow Fallback for Unsplittable Prompts

If a prompt exceeds capacity but has no `---` section boundaries to split on, `chunk_prompt_if_needed()` returns `[user_prompt]` (a single-element list) instead of `None`. This ensures the caller still processes it through the chunked code path (with logging and guards) rather than silently sending an oversized prompt to the API.

### Model Token Limits Registry

| Model | Max Context | Max Output |
|-------|------------|------------|
| `gpt-4o` | 128,000 | 16,384 |
| `gpt-4o-mini` | 128,000 | 16,384 |
| `gpt-4.1` / `gpt-4.1-2025-04-14` | 1,000,000 | 32,768 |
| `gpt-4.1-mini` | 1,000,000 | 32,768 |
| `gpt-5.3` | 1,000,000 | 32,768 |
| `o3-mini` | 128,000 | 16,384 |
| `claude-sonnet-4-20250514` | 200,000 | 8,192 |
| `claude-3.5-sonnet-20241022` | 200,000 | 8,192 |
| `gemini-2.5-pro` | 1,000,000 | 8,192 |
| `gemini-2.5-flash` | 1,000,000 | 8,192 |

Unknown models fall back to 128K context / 16K output.

### Key Functions (`token_utils.py`)

| Function | Purpose |
|----------|--------|
| `_default_model()` | Resolves the default model from `WorkflowConfig` (used as fallback for token counting) |
| `get_model_limits(model)` | Returns `(max_context, max_output)` for a model |
| `count_tokens(text, model)` | Count tokens using tiktoken (fallback: chars÷4). Model defaults to `_default_model()` if not provided |
| `count_messages_tokens(messages, model)` | Count tokens for a chat message list. Model defaults to `_default_model()` if not provided |
| `chunk_prompt_if_needed(system, user, model, max_completion, safety_margin)` | Returns `None` (fits) or `List[str]` (chunks) |
| `group_sources_by_budget(sources, base_tokens, model, max_completion, safety_margin)` | Group source keys into batches that fit context (used by Stage 7) |

### Console Output

During execution, the token budget and chunking decisions are logged to the console (visible in the UI):

```
[Proposal Compilation] Model gpt-4o: context=128,000, usable_for_prompt=79,616
[Proposal Compilation] Full prompt: 95,000 tokens (system=500, user=94,500)
[Proposal Compilation] Prompt exceeds usable context — using divide-and-accumulate strategy
[Proposal Compilation] Divided 6 sources into 2 group(s)
[Proposal Compilation] Group 1/2: Requirements Analysis, Tools & Technology Selection, Cloud & Infrastructure Planning
[Proposal Compilation] Capping max_completion_tokens: 16384 → 12000 (prompt=115,800, context=128,000)
...
```

---

## 17. Dynamic Currency System

Source: `cmbagent/phases/rfp/requirements_phase.py` (extraction), `cmbagent/phases/rfp/base.py` (3-pass detection + automatic injection)

### Problem

Previously, all cost figures were hardcoded to USD ($). Clients submitting RFPs in EUR, GBP, INR, or other currencies would receive proposals with incorrect currency.

### Solution: 3-Pass Currency Detection + Automatic Injection

**Stage 1 (Requirements Analysis)** extracts the currency from the RFP document:

```
10. **Currency** — Identify the currency used in the RFP (e.g., USD, EUR, GBP, INR).
    Look for currency symbols ($, €, £, ₹), currency codes, or country context.
    Search the ENTIRE RFP including payment terms, billing clauses, and annexures.
    Output:
    ## Currency
    **Primary Currency:** <CODE> (<SYMBOL>)
    If no currency is explicitly stated, default to USD ($).
```

**`RfpPhaseBase.get_currency_rule(context)`** uses a robust **3-pass detection** system:

```
Pass 1: Scan requirements analysis for structured output
  - Pattern A: **Primary Currency:** INR (₹)
  - Pattern B: looser — "Currency: INR" or "Payment — INR"

Pass 2: Scan original RFP text for explicit currency mentions
  - Currency names: "Indian Rupees", "British Pounds", etc.
  - ISO codes: INR, EUR, GBP, AUD, etc.
  - Currency symbols: ₹, €, £

Pass 3: Fallback to USD ($) only if no signal found in Pass 1 or 2
```

Supported currencies: USD, EUR, GBP, INR, AUD, CAD, JPY, CNY, SGD, AED, SAR, CHF.

**Automatic injection at base class level** — no individual phase can miss it:

| Agent | Injection Point | Code Location |
|-------|----------------|---------------|
| **Primary Agent** | Appended to `build_user_prompt()` output | `execute()` in `base.py` |
| **Specialist Agent** | Appended to specialist validation prompt | `_run_specialist()` in `base.py` |
| **Reviewer Agent** | Appended to review prompt | Review loop in `execute()` |

This means **all 7 stages × all 3 agents** (21 LLM calls) enforce the correct currency.

Additionally, individual phases (Tools, Cloud, Implementation, Proposal) include the currency rule explicitly in their `build_user_prompt()` — this is redundant but harmless (reinforced).

The review system prompt also uses generic "single consistent currency" language (item 9) so it validates whatever currency was selected.

---

## 18. Divide-and-Accumulate Strategy (Stage 7)

Source: `cmbagent/phases/rfp/proposal_phase.py`

### Problem

Stage 7 (Proposal Compilation) injects all 6 prior stage outputs into one prompt. For GPT-4o (128K context), the combined prompt frequently exceeds the context window. Simple truncation or condensation would lose critical data — cost figures, comparison tables, timelines.

### Solution: Zero-Data-Loss Divide-and-Accumulate

`RfpProposalPhase` overrides `execute()` with a custom strategy:

```
┌──────────────────────────────────────────────────────────────────────┐
│                  Stage 7 Execution Flow                              │
│                                                                      │
│  1. Build full prompt with all 6 source sections                     │
│  2. Count tokens: system + user prompt                               │
│                                                                      │
│  ┌──────────────── PATH A ────────────────┐                          │
│  │  Prompt fits (tokens ≤ usable_ctx)     │                          │
│  │  → Single generation call              │                          │
│  │  → If 0 chars returned → fall to B     │                          │
│  └────────────────────────────────────────┘                          │
│                                                                      │
│  ┌──────────────── PATH B ────────────────┐                          │
│  │  Prompt overflows or PATH A failed     │                          │
│  │                                         │                          │
│  │  1. group_sources_by_budget()           │                          │
│  │     → Divide 6 sources into N groups    │                          │
│  │     that each fit the context window    │                          │
│  │                                         │                          │
│  │  2. For each group:                     │                          │
│  │     → _build_partial_prompt()           │                          │
│  │       (only relevant proposal sections) │                          │
│  │     → _single_generate()               │                          │
│  │       (dynamic max_completion_tokens)   │                          │
│  │                                         │                          │
│  │  3. Accumulation pass:                  │                          │
│  │     → Merge all partials into one doc   │                          │
│  │     → Fix numbering, remove duplicates  │                          │
│  │     → Preserve 100% of content          │                          │
│  └────────────────────────────────────────┘                          │
│                                                                      │
│  4. Review pass (with chunking + dynamic cap)                        │
│  5. Save proposal.md                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

### Source-to-Section Mapping

Each source is mapped to specific proposal sections via `_SOURCE_TO_SECTIONS`:

| Source | Assigned Proposal Sections |
|--------|---------------------------|
| `requirements_analysis` | Cover Page, Executive Summary, Purpose & Introduction, Understanding of Requirements |
| `tools_technology` | Technology Stack & Tooling, Appendix B (Evaluation Matrices) |
| `cloud_infrastructure` | Cloud Infrastructure & Provider Selection, Appendix A (Cost Breakdowns) |
| `implementation_plan` | Methodology, Timeline & Milestones, Resources, Implementation Approach |
| `architecture_design` | Proposed Solution Overview, System Architecture, Appendix C (Charts & Data) |
| `execution_strategy` | Execution Plan, Risk Management, Qualifications, Compliance, Pricing, Terms, Appendices D & E |

### Key Functions

| Function | Purpose |
|----------|--------|
| `_get_sources(context)` | Extract 6 source outputs from `shared_state` |
| `_build_full_prompt(context, sources)` | Full prompt with all 6 sources + 19-section document structure |
| `_build_partial_prompt(context, keys, sources)` | Prompt for a subset of sources, targeting only their assigned sections |
| `_single_generate(client, resolved, prompt, is_reasoning, system_override)` | Single LLM call with dynamic `max_completion_tokens` capping |
| `group_sources_by_budget(sources, base_tokens, model, max_comp, margin)` | Greedy bin-packing of source keys into groups that fit the context window |

---

## 19. Refinement Chat Token Safety

Source: `backend/routers/rfp.py` — `refine_rfp_content()` endpoint

### Problem

The refinement chat (`POST /{task_id}/stages/{N}/refine`) sends the full stage content + user instruction to the LLM. For large stage outputs (especially Stage 7), this could exceed the model's context window and cause `ECONNRESET` or API errors.

### Solution

The refine endpoint now has:

1. **`timeout=300`** on the OpenAI client to prevent connection resets
2. **Dynamic `max_completion_tokens` capping** — same approach as phase execution
3. **Content trimming** — if the content exceeds the usable context, it is trimmed by taking the start and end of the content (preserving context from both halves) using tiktoken token-level encoding/decoding

```python
# If content is too large, trim to fit — take start + end
usable_for_content = int(max_ctx * 0.75) - sys_tokens - instruction_tokens - max_comp - 200
if content_tokens > usable_for_content:
    tokens = enc.encode(content)
    half = usable_for_content // 2
    trimmed_tokens = tokens[:half] + tokens[-half:]
    trimmed_content = enc.decode(trimmed_tokens)
```

---

## 20. End-to-End User Flow

### Step 0: Setup
1. User selects "RFP Proposal Generator" on Tasks page
2. Uploads RFP document (PDF auto-extracted to textarea) + optional context
3. Clicks "Analyze Requirements" → `POST /api/rfp/create` + `executeStage(1)` (button disables after first click to prevent duplicate submissions)

### Steps 1–6: Iterative Review
1. Stage executes in background (`_run_rfp_stage` → `phase.execute()`)
2. Live console output via WebSocket
3. On completion: split-view editor (60%) + refinement chat (40%)
4. User reviews, edits, refines → clicks "Next" → saves edits → triggers next stage

### Step 7: Proposal Compilation
1. `executeStage(7)` — all 6 prior outputs injected into prompt
2. LLM compiles comprehensive proposal with all sections + appendices
3. Success banner + PDF preview (resizable modal with embedded PDF viewer) + download links for all 7 artifacts

---

## 21. Error Handling

Stages fail for: LLM errors (empty response, API failure), infrastructure issues (rate limits, network), or data issues (missing shared state).

| Error | Fix |
|-------|-----|
| `openai.AuthenticationError` | Set valid `OPENAI_API_KEY` |
| `openai.RateLimitError` | Wait and retry, or use different model |
| Empty response | Retry (transient API issue) |
| `Stage N must be completed first` | Complete prior stages (strict ordering enforced) |
| Large prompt truncation (stages 5-7) | Automatic chunking handles this; or use model with larger context (GPT-4.1 = 1M tokens) |

Failures are: stored in `TaskStage.error_message`, logged with full traceback, sent via WebSocket as `stage_failed` event, shown in UI with Retry button.

---

## 22. Multi-Agent System

Source: `cmbagent/phases/rfp/agent_teams.py`, `cmbagent/phases/rfp/base.py`

Each RFP stage uses a **team of 3 specialised agents** that collaborate sequentially:

```
Primary Agent → Specialist Agent → Reviewer Agent
  (generate)       (validate)        (quality check)
```

### Configuration

- `multi_agent=True` (default) — enables the 3-agent pipeline
- `multi_agent=False` — reverts to the original 2-pass (generate → review) cycle
- `specialist_model` — override the specialist model for a specific phase (defaults from `get_phase_models()`)

### Model Assignments (Dynamic)

Defined in `agent_teams.py`. All agent roles use the **same model**, resolved dynamically from `WorkflowConfig.default_llm_model`:

| Stage | Primary | Specialist | Reviewer |
|-------|---------|-----------|----------|
| All (1–7) | (config) | (config) | (config) |

> **(config)** = `WorkflowConfig.default_llm_model`. Change in one place → changes everywhere.

### Token Safety

The specialist pass (`_run_specialist()` in `base.py`) has the same full token protection as all other LLM calls: `chunk_prompt_if_needed(safety_margin=0.75)` + dynamic `max_completion_tokens` capping. Enriched output must exceed 30% of original length to be accepted.

For full details, see the [Multi-Agent System section in rfp-proposal-generator.md](rfp-proposal-generator.md#15-multi-agent-system).

---

*Last updated: March 2026*
