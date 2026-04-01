# RFP Proposal Generator — Complete Feature Guide

> **MARS Platform · AI-Powered Technical Proposal Generation**
>
> A comprehensive guide covering every aspect of the RFP Proposal Generator feature: fundamentals, workflow stages, task lifecycle, outcome processing, AI techniques, and architecture.

---

## Table of Contents

1. [Basics — What Is the RFP Proposal Generator?](#1-basics--what-is-the-rfp-proposal-generator)
2. [All Steps Used in the Workflow](#2-all-steps-used-in-the-workflow)
3. [Task Flow — From `/tasks` to Final Proposal](#3-task-flow--from-tasks-to-final-proposal)
4. [Outcomes — Saved and Processed](#4-outcomes--saved-and-processed)
5. [AI Techniques Used](#5-ai-techniques-used)
6. [Architecture Deep Dive](#6-architecture-deep-dive)
7. [API Reference (Quick)](#7-api-reference-quick)
8. [Configuration & Model Defaults](#8-configuration--model-defaults)
9. [Error Handling & Troubleshooting](#9-error-handling--troubleshooting)
10. [Glossary](#10-glossary)
11. [Complete Flow Explanation — Classes, Functions & Agents](#11-complete-flow-explanation--classes-functions--agents)
12. [Token Capacity Management](#12-token-capacity-management)
13. [Dynamic Currency System](#13-dynamic-currency-system)
14. [Divide-and-Accumulate Strategy (Stage 7)](#14-divide-and-accumulate-strategy-stage-7)
15. [Multi-Agent System](#15-multi-agent-system)

---

## 1. Basics — What Is the RFP Proposal Generator?

### 1.1 Overview

The RFP Proposal Generator is a **7-stage, human-in-the-loop AI workflow** built into the MARS platform. It transforms a raw RFP (Request for Proposal) document into a **complete, professional technical proposal** — from requirements analysis through architecture design to the final compiled document — while keeping the human in control at every step.

The feature is registered under the mode **`rfp-proposal`** and appears in the UI as **"RFP Proposal Generator"** on the Tasks page.

### 1.2 What It Produces

Starting from an RFP document, the system outputs:

| Artifact | Format | Description |
|---|---|---|
| Requirements Analysis | Markdown | Structured functional, non-functional, stakeholders, risks |
| Tools & Technology | Markdown | Complete tool selection with per-tool cost estimates and comparison tables |
| Cloud & Infrastructure | Markdown | Cloud architecture design with itemized cost breakdown and provider comparison |
| Implementation Plan | Markdown | Phased delivery roadmap with timeline, sprints, and budget |
| Architecture Design | Markdown | System architecture with component diagrams and ADRs |
| Execution Strategy | Markdown | Full execution strategy from kickoff to post-launch |
| **Compiled Proposal** | Markdown | **Final compiled proposal** with executive summary, pricing, and appendices |

### 1.3 Key Design Principles

| Principle | How It's Implemented |
|---|---|
| **Phase-Based Execution** | Each stage runs as an `RfpPhaseBase` subclass with a 3-agent pipeline: primary → specialist → reviewer (3+ LLM calls per stage) |
| **Multi-Agent Collaboration** | Each stage uses a team of 3 specialised agents with different models optimised for their role |
| **Human-in-the-loop** | Users can review, edit, and refine AI output between every stage |
| **Progressive context** | Each stage builds on all previous stages (cumulative shared state) |
| **Real-time feedback** | WebSocket streaming + REST polling deliver live console output during execution |
| **Resumable** | Tasks persist in a database and can be resumed after page reloads or interruptions |
| **Cost-transparent** | Per-LLM-call cost tracking is aggregated and displayed throughout the workflow |
| **Editable at every stage** | Split-view editor (60% preview + 40% refinement chat) |
| **Token-safe** | Every LLM call has dynamic `max_completion_tokens` capping and automatic prompt chunking (0.75 safety margin) |
| **Dynamic currency** | Currency is extracted from the RFP (Stage 1) and propagated to all cost-producing stages; defaults to USD ($) |
| **Zero data loss** | Stage 7 uses a divide-and-accumulate strategy — no source data is ever truncated, condensed, or dropped |

### 1.4 Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python, FastAPI, SQLAlchemy, asyncio, OpenAI API |
| **Phase System** | `RfpPhaseBase` → 7 phase subclasses with generate→review cycles |
| **Frontend** | React, TypeScript, Next.js |
| **Real-time** | WebSocket + REST polling |
| **Database** | SQLite (via SQLAlchemy ORM) |
| **Default LLM** | Dynamic from `WorkflowConfig.default_llm_model` (configurable per stage via `config_overrides`) |

### 1.5 Orchestration Model — Phase-Based (Generate → Review)

The RFP Proposal Generator uses the **Phase-Based** orchestration model with a custom `RfpPhaseBase` class hierarchy:

| Orchestration | Used By | How It Works |
|---|---|---|
| **Phase-Based (RFP)** | **RFP Proposal Generator** | Each stage dynamically loads an `RfpPhaseBase` subclass via `_load_phase_class()`. The phase executes a generate → review cycle: 1 generation LLM call + 1 review LLM call per stage. Phase classes are in `cmbagent/phases/rfp/`. |
| **SwarmOrchestrator** | Copilot, Planning & Control (swarm) | Loads all agent classes into a unified swarm with dynamic routing. |
| **PhaseOrchestrator** | Deep Research, Planning & Control (classic) | Sequential phases from `PhaseRegistry`, each invoking agent classes. |

**Why Phase-Based for RFP:**

1. **Expert personas** — 7 phase classes each define a domain-specific system prompt (business analyst, cloud architect, etc.)
2. **3-agent pipeline** — Each phase makes 3 LLM calls (when `multi_agent=True`, the default): Primary (generate) → Specialist (validate & enrich) → Reviewer (13-point quality checklist). Set `multi_agent=False` for the original 2-call generate→review cycle.
3. **Cumulative context** — Each phase's `build_user_prompt()` injects all prior stages' output from shared state
4. **Human-in-the-loop** — Users review and edit between every stage via the split-view editor
5. **Quality enforcement** — The specialist and reviewer passes enforce consistent currency (dynamically detected from the RFP), cost table completeness, no placeholders, comparison tables, and security assessments

The `WorkflowRun` record stores `agent="phase_orchestrator"` and `meta.orchestration="phase-based"` to identify this execution model.

---

## 2. All Steps Used in the Workflow

The RFP Proposal Generator is an **8-step wizard** in the UI, mapping to **7 backend stages**:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  WIZARD STEP 0        STEP 1         STEP 2       STEP 3      STEP 4           │
│  ─────────────     ───────────    ──────────    ──────────   ──────────         │
│  Setup Panel  ──►  Requirements ──► Tools ────► Cloud/Infra ──► Impl. Plan ──► │
│  (no stage)        (Stage 1)       (Stage 2)    (Stage 3)      (Stage 4)       │
│                                                                                  │
│  ... STEP 5       STEP 6       STEP 7                                           │
│  ──────────    ──────────   ───────────                                         │
│  ──► Arch. ──► Execution ──► Proposal                                           │
│    (Stage 5)   (Stage 6)    (Stage 7)                                           │
│                                                                                  │
│  User enters     Phase class      User reviews/edits    Phase generates          │
│  RFP text +      generates →      with split-view       next section using       │
│  uploads docs    reviews output   editor + chat         all prior context        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Step 0 — Setup (No Backend Stage)

**UI Component:** `RfpSetupPanel.tsx`

| Action | Details |
|---|---|
| Upload RFP documents | Drag-and-drop zone at top; supports PDF, DOCX, TXT, CSV, JSON, and more — PDF text auto-populates the RFP textarea |
| Enter RFP content | Free-text area — paste the full RFP or describe project requirements (required) |
| Enter additional context | Organization info, budget range, preferences, constraints (optional) |
| Click "Analyze Requirements" | Triggers task creation + Stage 1 execution |

**On submit:** `POST /api/rfp/create` → creates `WorkflowRun` + 7 `TaskStage` records → auto-executes Stage 1

### Steps 1–6 — Stage Review & Editing

**UI Component:** `RfpReviewPanel.tsx` (reused per stage)

| Feature | Details |
|---|---|
| **Split view** | 60% markdown editor/preview + 40% refinement chat |
| **Auto-save** | Content saved to DB + disk after 1s debounce on edit |
| **AI refinement** | User types instruction → LLM refines content → user clicks "Apply" |
| **Next button** | Saves edits, then triggers next stage's phase execution |
| **Execution progress** | Real-time console output via WebSocket + timer + cost display |

### Step 7 — Proposal Compilation

**UI Component:** `RfpProposalPanel.tsx`

| Feature | Details |
|---|---|
| Success banner | "Proposal Generated Successfully" with checkmark |
| PDF preview | Resizable modal with embedded PDF viewer (`?inline=true`) |
| Proposal preview | Full rendered markdown of the compiled proposal |
| Download | Links for all 7 `.md` artifact files + PDF download |
| Cost summary | Total cost across all stages |

**Backend execution:** Uses the **divide-and-accumulate** strategy for zero data loss — see [Section 14](#14-divide-and-accumulate-strategy-stage-7).

---

## 3. Task Flow — From `/tasks` to Final Proposal

### 3.1 Task Creation

```
User clicks "RFP Proposal Generator" in TaskList.tsx
  │
  └── RfpProposalTask.tsx renders the 8-step wizard
       │
       ├── Step 0: RfpSetupPanel.tsx
       │     ├── User uploads PDF → pdf_extractor.py extracts text → auto-fills textarea
       │     ├── User enters/edits RFP content + additional context
       │     └── Clicks "Analyze Requirements"
       │
       └── hook.createTask(text, context, stageConfig)    [useRfpTask.ts]
             └── POST /api/rfp/create
                   └── create_rfp_task()                   [rfp.py]
                         ├── SessionManager.create_session(mode="rfp-proposal")
                         ├── Create WorkflowRun (agent="phase_orchestrator")
                         ├── Create 7 TaskStage records (all "pending")
                         ├── Write rfp_input.md + rfp_context.md to disk
                         └── Return task_id, work_dir, stages[]
```

### 3.2 Stage Execution (Phase-Based Generate → Review)

```
hook.executeStage(N, taskId)                              [useRfpTask.ts]
  │
  ├── POST /api/rfp/{id}/stages/{N}/execute               [rfp.py]
  │     ├── VALIDATE: all stages 1..N-1 are "completed"
  │     ├── Mark stage N as "running"
  │     ├── build_shared_state(up_to=N) → cumulative dict
  │     ├── _build_rfp_context(work_dir) → uploaded file text
  │     └── asyncio.create_task(_run_rfp_stage(...))
  │
  └── _run_rfp_stage()                                     [rfp.py]
        ├── 1. _ConsoleCapture → intercept stdout/stderr
        ├── 2. _load_phase_class(N) → e.g. RfpToolsPhase
        ├── 3. Instantiate phase with RfpPhaseConfig(model, n_reviews)
        ├── 4. Build PhaseContext(task, work_dir, shared_state)
        │
        ├── 5. await phase.execute(ctx)                    [base.py]
        │     ├── GENERATION PASS (LLM call 1):
        │     │   system = phase.system_prompt  (expert persona)
        │     │   user   = phase.build_user_prompt(ctx) (RFP + prior stages)
        │     │   → draft content
        │     │
        │     └── REVIEW PASS (LLM call 2):
        │         system = phase.review_system_prompt  (13-point checklist)
        │         user   = "Draft document:\n\n{draft}"
        │         → improved content
        │
        ├── 6. Extract content from PhaseResult
        ├── 7. CostRepository.record_cost(tokens, cost_usd)
        ├── 8. Save to {work_dir}/input_files/{file}.md
        ├── 9. Update stage output_data + mark "completed"
        └── 10. Restore stdout/stderr
```

### 3.3 Human Review Loop (Steps 1–6)

```
WebSocket receives "stage_completed"
  │
  ├── fetchStageContent(N) → loads generated content into editor
  ├── Split-view: Editor/Preview (60%) + Refinement Chat (40%)
  │
  ├── USER ACTIONS:
  │     ├── Edit markdown directly → auto-save after 1s debounce
  │     │     └── PUT /api/rfp/{id}/stages/{N}/content
  │     │           → updates DB shared_state + rewrites .md file
  │     │
  │     ├── Use Refinement Chat → AI improves content
  │     │     └── POST /api/rfp/{id}/stages/{N}/refine
  │     │           → LLM call with "Refine this content based on: {instruction}"
  │     │           → User clicks "Apply" to accept
  │     │
  │     └── Click "Next" → saves edits → auto-triggers next phase execution
  │
  └── Edits are saved to BOTH DB and filesystem
      └── Next phase reads the edited version via shared_state
```

### 3.4 Proposal Compilation (Step 7)

```
Stage 7 RfpProposalPhase receives ALL 6 prior stages' content
  │
  ├── Token capacity check (0.75 safety margin)
  │
  ├── PATH A: Prompt fits → single generation call (dynamic max_completion_tokens)
  │   └── If empty/short output → automatic fallback to PATH B
  │
  ├── PATH B: Prompt overflows
  │   ├── group_sources_by_budget() → divide 6 sources into N groups
  │   ├── For each group: _build_partial_prompt() → _single_generate()
  │   └── Accumulation pass: merge partials into one document (zero data loss)
  │
  ├── Review pass: chunk_prompt_if_needed() + dynamic cap → enterprise polish
  └── Saves final proposal.md
       │
       └── UI shows:
             ├── "Proposal Generated Successfully" banner
             ├── PDF preview (resizable modal)
             ├── Download links for all 7 artifacts
             └── Cost summary
```

### 3.5 Real-Time Monitoring

During stage execution, two parallel channels deliver updates:

| Channel | What It Delivers | Frequency |
|---|---|---|
| **REST Polling** | Console output lines (`GET /stages/{N}/console?since=X`) | Every 2 seconds |
| **WebSocket** | `stage_completed` / `stage_failed` events | Immediate |

Console output is captured via `_ConsoleCapture` — a thread-safe class that intercepts stdout/stderr and writes to both the server terminal and a shared in-memory buffer.

### 3.6 Task Resumption

Tasks are fully persistent and can be resumed:

1. `GET /api/rfp/recent` lists incomplete tasks (status="executing")
2. User selects a task → `GET /api/rfp/{id}` loads full state
3. UI reconstructs the wizard position:
   - Running stage → reconnect WebSocket + resume console polling
   - Completed stage → show content in editor (editable)
   - Pending/failed stage → stop at that step (user can retry)

---

## 4. Outcomes — Saved and Processed

### 4.1 File System Layout

Every task gets a dedicated directory:

```
{session_id}/tasks/{task_id}/
│
├── input_files/
│   ├── rfp_input.md          ◄── Original RFP text (from Setup)
│   ├── rfp_context.md        ◄── Additional context (from Setup)
│   ├── *.pdf, *.docx, ...    ◄── User-uploaded RFP documents
│   ├── requirements.md       ◄── Stage 1 output (editable)
│   ├── tools.md              ◄── Stage 2 output (editable)
│   ├── cloud.md              ◄── Stage 3 output (editable)
│   ├── implementation.md     ◄── Stage 4 output (editable)
│   ├── architecture.md       ◄── Stage 5 output (editable)
│   ├── execution.md          ◄── Stage 6 output (editable)
│   └── proposal.md           ◄── Stage 7 output (final compiled proposal)
```

### 4.2 Database Records

Each task creates:

| Model | Count | Purpose |
|---|---|---|
| **Session** | 1 | Groups all records; supports suspend/resume (mode="rfp-proposal") |
| **WorkflowRun** | 1 | Parent task record (mode, status, work_dir, config, task_description) |
| **TaskStage** | 7 | One per stage (status, input_data, output_data, timing, error_message) |
| **CostRecord** | 21+ | One per LLM call: 7 stages × 3 agents (primary + specialist + reviewer) + Stage 7 divide-and-accumulate calls + any refinement calls |

### 4.3 Shared State — Cumulative Context

```
Stage 1 completes → shared_state = {
    requirements_analysis: "..."
}
Stage 2 completes → shared_state = {
    requirements_analysis: "...",
    tools_technology: "..."
}
...
Stage 7 → reads ALL 6 keys to compile final proposal
```

**Reconstruction:** Before each stage, `build_shared_state()` scans all completed prior stages and merges their `output_data["shared"]` dictionaries.

### 4.4 Output Processing Per Stage

| Stage | Phase Class | Output Key | File |
|---|---|---|---|
| 1 | `RfpRequirementsPhase` | `requirements_analysis` | `requirements.md` |
| 2 | `RfpToolsPhase` | `tools_technology` | `tools.md` |
| 3 | `RfpCloudPhase` | `cloud_infrastructure` | `cloud.md` |
| 4 | `RfpImplementationPhase` | `implementation_plan` | `implementation.md` |
| 5 | `RfpArchitecturePhase` | `architecture_design` | `architecture.md` |
| 6 | `RfpExecutionPhase` | `execution_strategy` | `execution.md` |
| 7 | `RfpProposalPhase` | `proposal_compilation` | `proposal.md` |

### 4.5 Human Edits — Dual Persistence

When a user edits stage content, edits are saved in **two places** simultaneously:

1. **Database:** `output_data["shared"][key]` is updated in the `TaskStage` record
2. **Filesystem:** The corresponding `.md` file is overwritten

This ensures the next stage reads the human-edited version and task resumption restores the latest content.

### 4.6 Stage Definition Mapping

```python
STAGE_DEFS = [
    {"number": 1, "name": "requirements_analysis",  "shared_key": "requirements_analysis",  "file": "requirements.md"},
    {"number": 2, "name": "tools_technology",        "shared_key": "tools_technology",       "file": "tools.md"},
    {"number": 3, "name": "cloud_infrastructure",    "shared_key": "cloud_infrastructure",   "file": "cloud.md"},
    {"number": 4, "name": "implementation_plan",     "shared_key": "implementation_plan",    "file": "implementation.md"},
    {"number": 5, "name": "architecture_design",     "shared_key": "architecture_design",    "file": "architecture.md"},
    {"number": 6, "name": "execution_strategy",      "shared_key": "execution_strategy",     "file": "execution.md"},
    {"number": 7, "name": "proposal_compilation",    "shared_key": "proposal_compilation",   "file": "proposal.md"},
]
```

---

## 5. AI Techniques Used

### 5.1 Phase-Based Generate → Review Cycle

Each of the 7 stages uses a dedicated `RfpPhaseBase` subclass that runs a **two-pass execution model**:

**Pass 1 — Generation:** The phase's `system_prompt` defines an expert AI persona. The `build_user_prompt(context)` method constructs the full prompt including RFP content, uploaded file context, and all prior stages' output from `shared_state`.

**Pass 2 — Review:** A shared `review_system_prompt` (defined in `RfpPhaseBase`) acts as a senior proposal reviewer with a **13-point quality checklist**. The reviewer receives the draft and improves it to professional submission quality.

```
Generation prompt structure:
  system: "You are a [domain expert persona]..."
  user:   phase.build_user_prompt(context)
          → includes RFP text, uploaded files, all prior stage outputs

Review prompt structure:
  system: "You are a senior proposal reviewer...  Specifically:
           1. Fix factual errors...
           2. Ensure all cost figures...
           ...13 checklist items..."
  user:   "Draft document:\n\n{generated_content}"
```

### 5.2 Cumulative Context Injection

Each phase's `build_user_prompt()` reads from `context.shared_state`, which grows with each completed stage:

```
Stage 1: RFP content + uploaded docs
Stage 2: requirements_analysis (from Stage 1)
Stage 3: requirements_analysis + tools_technology (Stages 1–2)
Stage 4: requirements + tools + cloud (Stages 1–3)
Stage 5: requirements + tools + cloud + implementation (Stages 1–4)
Stage 6: all 5 prior stages
Stage 7: ALL 6 prior stages (full proposal context)
```

### 5.3 Role-Based Expert Personas

Each phase class defines a specialized system prompt optimized for that stage:

| Stage | Phase Class | AI Persona | Expertise |
|---|---|---|---|
| 1 | `RfpRequirementsPhase` | Expert Business Analyst (15+ years) | Requirements extraction, risk identification, stakeholder mapping, budget analysis |
| 2 | `RfpToolsPhase` | Senior Solutions Architect (20+ years) | Technology evaluation, head-to-head comparisons, licensing analysis, security assessment |
| 3 | `RfpCloudPhase` | Cloud Infrastructure Architect (20+ years, AWS/Azure/GCP) | Provider comparison, IaC, cost optimization, managed services evaluation |
| 4 | `RfpImplementationPhase` | Senior Project Manager & Delivery Lead | Timeline planning, sprint structure, resource allocation, quality gates |
| 5 | `RfpArchitecturePhase` | Principal System Architect | System design, component boundaries, data architecture, ADRs |
| 6 | `RfpExecutionPhase` | Delivery Executive & Program Manager | Go-live planning, CI/CD, testing strategy, governance, KPIs |
| 7 | `RfpProposalPhase` | World-Class Proposal Writer (Fortune 500, $10M–$500M) | Executive summary, document assembly, pricing tables, appendices |

### 5.4 Review System Prompt — 13-Point Quality Checklist

The shared review prompt (inherited from `RfpPhaseBase`) enforces:

1. Fix factual errors, strengthen weak sections, add missing detail
2. Improve structure and flow, ensure proper section numbering
3. Ensure ALL cost figures are present, consistent, and fit within budget
4. Verify every tool/technology has a comparison table vs alternatives
5. Verify security features are compared for each major tool and service
6. Verify cloud provider comparison and justification are thorough
7. Add professional tables where data is listed as bullets
8. Replace ANY placeholder text (`[Insert ...]`, `[To be added]`) with ACTUAL content
9. Ensure ALL monetary values use a single consistent currency throughout (dynamically detected from the RFP; defaults to USD if not found) — no mixed currencies
10. Verify every cost table has Monthly and Annual columns with actual dollar figures
11. Verify Annual Cost = Monthly Cost × 12 (fix math errors)
12. Verify appendices contain REAL content (full tables, glossary entries, references)
13. Ensure the document reads as a polished enterprise proposal — not an AI summary

### 5.5 Human-in-the-Loop Refinement

Between every stage, users can:
- **Direct edit** — Modify the generated markdown in the split-view editor
- **AI refinement** — Give natural language instructions to improve content

The refinement uses a **separate LLM call** with a dedicated system prompt and full **token safety protection**:

```
System: "You are a technical proposal consultant. Refine the following content
         based on the user's instruction. Return ONLY the refined markdown
         content, no explanations."
User:   "Current content:\n\n{content}\n\n---\n\nInstruction: {user_message}"
```

Model: dynamic from `WorkflowConfig`, Temperature: `0.7`, Max completion tokens: dynamically capped

**Token safety:** The refine endpoint checks token capacity before calling the LLM. If the content exceeds the usable context window, it is **trimmed** by taking the start and end of the content (preserving context from both halves) using tiktoken token-level encoding/decoding. The OpenAI client uses `timeout=300` to prevent connection resets on large content.

### 5.6 File Context Augmentation

Uploaded RFP documents are scanned by `_build_rfp_context()` and their content is injected into the prompt:

| File Type | Extraction Method |
|---|---|
| `.pdf` | Rich extraction via `pdf_extractor.py` — text, tables (markdown), image descriptions (up to 500KB) |
| `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html` | Full content preview (first 4KB) |
| Other files | Metadata only (name, size, path) |

Braces in extracted content are escaped (`{` → `{{`) to prevent `str.format()` interpretation.

### 5.7 Prompt Engineering Patterns

| Pattern | Description | Used In |
|---|---|---|
| **Persona prompting** | "You are a [role]" — each phase has a domain expert persona | All 7 phase `system_prompt` properties |
| **Generate → review** | Draft generation followed by specialist validation then quality review pass | `RfpPhaseBase.execute()` |
| **Multi-agent teams** | 3-agent pipeline (Primary → Specialist → Reviewer) using different models per role | `agent_teams.py`, `_run_specialist()` |
| **Structured output** | Explicit section headings, numbered requirements, table formats | All 7 phase `build_user_prompt()` methods |
| **Cumulative context** | Prior stages' output injected as reference material | `build_user_prompt()` reads `context.shared_state` |
| **Constraint enforcement** | Dynamic currency from RFP, no placeholders, comparison tables required | `review_system_prompt` 13-point checklist, `get_currency_rule()` |
| **Token capacity management** | Automatic prompt chunking and dynamic `max_completion_tokens` capping at every LLM call | `token_utils.py`, `RfpPhaseBase.execute()` |
| **Divide-and-accumulate** | Zero-data-loss source grouping and merging for Stage 7 | `RfpProposalPhase.execute()`, `group_sources_by_budget()` |
| **Budget awareness** | Stage 1 extracts budget; downstream stages must respect it | Stages 2, 3, 4 prompts reference budget from requirements |

---

## 6. Architecture Deep Dive

### 6.1 Phase Class Hierarchy

```
Phase (cmbagent/phases/base.py)                    # Abstract base
  └── RfpPhaseBase (cmbagent/phases/rfp/base.py)   # Generate→review engine
        ├── RfpRequirementsPhase                    # Stage 1
        ├── RfpToolsPhase                           # Stage 2
        ├── RfpCloudPhase                           # Stage 3
        ├── RfpImplementationPhase                  # Stage 4
        ├── RfpArchitecturePhase                    # Stage 5
        ├── RfpExecutionPhase                       # Stage 6
        └── RfpProposalPhase                        # Stage 7
```

Each subclass provides:
- `phase_type` — Identifier (e.g., `"rfp_requirements"`)
- `display_name` — Human-readable label
- `shared_output_key` — Key in shared_state dict
- `output_filename` — File to write output to
- `system_prompt` — Expert persona (generation pass)
- `build_user_prompt(context)` — Full prompt construction

### 6.2 RfpPhaseConfig

```python
@dataclass
class RfpPhaseConfig(PhaseConfig):
    model: str = field(default_factory=_default_model)  # resolved from WorkflowConfig
    temperature: float = 0.7
    max_completion_tokens: int = 16384
    n_reviews: int = 1              # 0 = single-shot, 1+ = generate → review
    review_model: Optional[str] = None  # defaults to same as model
```

> **Note:** `_default_model()` resolves the model dynamically from `WorkflowConfig.default_llm_model` at runtime. No model name is hardcoded — changing the config changes all stages.

> **Note:** The `temperature` parameter is automatically omitted for reasoning models (o3-mini, o1-*) that do not support it.

### 6.3 Dynamic Phase Loading

Phases are loaded via `importlib` to avoid circular imports:

```python
_PHASE_CLASSES = {
    1: "cmbagent.phases.rfp.requirements_phase:RfpRequirementsPhase",
    2: "cmbagent.phases.rfp.tools_phase:RfpToolsPhase",
    3: "cmbagent.phases.rfp.cloud_phase:RfpCloudPhase",
    4: "cmbagent.phases.rfp.implementation_phase:RfpImplementationPhase",
    5: "cmbagent.phases.rfp.architecture_phase:RfpArchitecturePhase",
    6: "cmbagent.phases.rfp.execution_phase:RfpExecutionPhase",
    7: "cmbagent.phases.rfp.proposal_phase:RfpProposalPhase",
}

def _load_phase_class(stage_num):
    import importlib
    ref = _PHASE_CLASSES[stage_num]
    module_path, cls_name = ref.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)
```

### 6.4 Console Capture

`_ConsoleCapture` is a thread-safe stdout/stderr interceptor:

```
_ConsoleCapture (per stage)
    │
    ├── write(text) → original stdout (server logs)
    │              → _console_buffers["{task_id}:{stage_num}"] (shared buffer)
    │
    └── Exposed via:
         ├── REST: GET /api/rfp/{id}/stages/{N}/console?since=X
         └── WebSocket: /ws/rfp/{id}/{N} → polls buffer every 1s
```

### 6.5 End-to-End Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MARS UI (Next.js)                            │
│                                                                     │
│  TaskList.tsx → RfpProposalTask.tsx (8-step wizard)                 │
│    ├── RfpSetupPanel.tsx     (Step 0: input + upload)               │
│    ├── RfpReviewPanel.tsx    (Steps 1–6: edit + refine)             │
│    ├── RfpExecutionPanel.tsx (per-stage progress + console)         │
│    └── RfpProposalPanel.tsx  (Step 7: final proposal + download)    │
│                                                                     │
│  useRfpTask.ts (React hook — state, API calls, WebSocket)           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Python)                         │
│                                                                     │
│  routers/rfp.py                                                     │
│    ├── create_rfp_task()  → Session + WorkflowRun + 7 TaskStages   │
│    ├── execute_rfp_stage()                                          │
│    │     ├── build_shared_state()                                   │
│    │     ├── _build_rfp_context()                                   │
│    │     └── asyncio.create_task(_run_rfp_stage(...))               │
│    ├── _run_rfp_stage()                                             │
│    │     ├── _load_phase_class(N) → e.g. RfpToolsPhase             │
│    │     ├── PhaseContext(task, shared_state, work_dir)              │
│    │     ├── await phase.execute(ctx) → generate → review           │
│    │     ├── CostRepository.record_cost(...)                        │
│    │     └── TaskStageRepository.update_stage_status(...)           │
│    ├── refine_rfp_content() → separate LLM call                    │
│    └── reset_from_stage()   → reset to pending, delete files        │
│                                                                     │
│  main.py → WebSocket /ws/rfp/{task_id}/{stage_num}                  │
│  services/pdf_extractor.py → text + tables + images from PDFs       │
│                                                                     │
│  cmbagent/phases/rfp/                                               │
│    ├── base.py → RfpPhaseBase (generate→review engine)              │
│    └── *_phase.py → 7 phase subclasses with expert prompts          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Data Storage Layer                              │
│  ┌──────────────┐    ┌───────────────────────────────────┐          │
│  │   SQLite DB   │    │  File System (work_dir/)           │          │
│  │  cmbagent.db  │    │  └── input_files/                  │          │
│  │               │    │       ├── rfp_input.md              │          │
│  │  - sessions   │    │       ├── rfp_context.md            │          │
│  │  - workflow_  │    │       ├── requirements.md           │          │
│  │    runs       │    │       ├── tools.md                  │          │
│  │  - task_      │    │       ├── cloud.md, impl, arch, ..  │          │
│  │    stages     │    │       ├── execution.md              │          │
│  │  - cost_      │    │       └── proposal.md               │          │
│  │    records    │    └───────────────────────────────────┘          │
│  └──────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. API Reference (Quick)

All endpoints prefixed with `/api/rfp/`. Source: `backend/routers/rfp.py`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/create` | Create new task (Session + WorkflowRun + 7 stages) |
| PATCH | `/{id}/description` | Update RFP text/context (for auto-created tasks) |
| GET | `/recent` | List up to 10 incomplete tasks for resume flow |
| GET | `/{id}` | Full task state (stages, progress %, cost) |
| POST | `/{id}/stages/{N}/execute` | Execute stage via phase class |
| GET | `/{id}/stages/{N}/content` | Get stage output content |
| PUT | `/{id}/stages/{N}/content` | Save user edits (DB + file) |
| POST | `/{id}/stages/{N}/refine` | LLM refinement of content |
| GET | `/{id}/stages/{N}/console` | Console output lines (polling) |
| POST | `/{id}/reset-from/{N}` | Reset stage N+ to pending, delete files |
| GET | `/{id}/download/{filename}` | Download artifact (validated filename) |
| DELETE | `/{id}` | Delete task + `shutil.rmtree(work_dir)` |
| WS | `/ws/rfp/{id}/{N}` | Real-time console + completion events |

---

## 8. Configuration & Model Defaults

### 8.1 Phase Model Defaults (RfpPhaseConfig)

| Parameter | Default | Notes |
|---|---|---|
| `model` | Dynamic (`_default_model()`) | Resolved from `WorkflowConfig.default_llm_model` at runtime; overridable via `config_overrides` |
| `temperature` | `0.7` | Balances creativity and coherence (omitted for reasoning models) |
| `max_completion_tokens` | `16,384` | Large enough for detailed sections |
| `n_reviews` | `1` | 1 review pass per stage |
| `review_model` | `None` (same as model) | Can be set separately for review pass |
| `multi_agent` | `True` | Enable 3-agent pipeline (primary → specialist → reviewer). Set `False` for 2-pass generate→review. |
| `specialist_model` | `None` (per-stage) | Override specialist model; defaults from `get_phase_models()` |

### 8.2 Dynamic Model Resolution

All stages resolve their model dynamically from `WorkflowConfig.default_llm_model` — **no model names are hardcoded**.

The resolution chain:
1. `_get_default_rfp_model()` in `backend/routers/rfp.py` reads from `WorkflowConfig`
2. `_default_model()` in `base.py` reads from `WorkflowConfig` (used by `RfpPhaseConfig.model`)
3. `_cfg_model()` in `agent_teams.py` reads from `WorkflowConfig` (used by `get_phase_models()`)
4. `_default_model()` in `token_utils.py` reads from `WorkflowConfig` (used by `count_tokens()` default)

All 7 stages × all 3 agents (primary, specialist, reviewer) use the **same configured model**.

> **Azure deployment:** Ensure `AZURE_OPENAI_DEPLOYMENT` is set to your deployment name.
> Set `CMBAGENT_DEFAULT_MODEL` environment variable or update `WorkflowConfig` to change the model for all stages.

### 8.3 Model Override

Override the model per stage via `config_overrides` in the execute request:

```json
{
  "config_overrides": {
    "model": "gpt-4.1",
    "n_reviews": 2
  }
}
```

### 8.4 Available Models

| Model | Best For |
|---|---|
| `gpt-4o` | Good balance of speed, quality, and availability |
| `gpt-4.1` | Strong analytical and writing quality |
| `gpt-4.1-mini` | Cost-effective with 1M context window |
| `gpt-4o-mini` | Faster and cheaper — good for iteration |
| `gpt-5.3` | Best reasoning and largest output window |
| `o3-mini` | Reasoning-focused tasks (does not support `temperature`) |
| `gemini-2.5-flash` | Cost-effective for long outputs (requires Gemini API key) |
| `claude-sonnet-4` | Alternative provider (requires Anthropic API key) |

> **Note:** The default model is resolved from `WorkflowConfig.default_llm_model`. All models in this table are supported and can be set globally or per-stage.

### 8.5 Required Environment Variables

| Variable | Required? | Used By |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | All 7 stages (generation + review) + refinement |
| `ANTHROPIC_API_KEY` | Optional | If using Anthropic models via override |
| `GOOGLE_API_KEY` | Optional | If using Gemini models via override |

### 8.6 Server Configuration

| Setting | Value |
|---|---|
| **Backend Port** | `8000` |
| **Frontend Port** | `3000` |
| **API Docs** | `http://localhost:8000/docs` |
| **WebSocket** | `ws://localhost:8000/ws/rfp/{id}/{N}` |

### 8.7 Supported Upload File Types

`.pdf`, `.docx`, `.doc`, `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`

---

## 9. Error Handling & Troubleshooting

### 9.1 Common Errors

#### All Stages

| Error | Cause | Fix |
|---|---|---|
| `Stage {N} ({name}) must be completed first` | Previous stages incomplete | Complete all prior stages |
| `Stage is already running` | Duplicate execution request | Wait for current execution |
| `Task not found` | Invalid task_id | Check task_id from `/api/rfp/recent` |

#### Stage 1 — Requirements Analysis

| Error | Cause | Fix |
|---|---|---|
| Empty output | Model returned empty response | Retry; verify `OPENAI_API_KEY` validity |
| Very short analysis | Insufficient RFP input | Provide more detailed RFP content |

#### Stage 7 — Proposal Compilation

| Error | Cause | Fix |
|---|---|---|
| Incomplete sections | Model context window exceeded | Use a model with larger context window |
| Missing cost tables | Prior stages' tools/cloud data was thin | Edit Stages 2–3 to add more cost detail before re-running Stage 7 |

### 9.2 Diagnostics

**Check stage error:**
```bash
curl http://localhost:8000/api/rfp/{task_id}/stages/{stage_num}/content
```

**Check full task status:**
```bash
curl http://localhost:8000/api/rfp/{task_id}
```

**Check via database:**
```sql
SELECT stage_number, status, error_message FROM task_stages
WHERE parent_run_id = '{task_id}' ORDER BY stage_number;
```

### 9.3 Retry Behavior

- Failed stages show error + **Retry** button in the UI
- Retries re-run the phase from scratch (generate → review)
- Previous stages' outputs are preserved in shared_state
- Console buffers are reset on retry

---

## 10. Glossary

| Term | Definition |
|---|---|
| **Phase class** | An `RfpPhaseBase` subclass that encapsulates a stage's system prompt, user prompt builder, and 3-agent execution logic |
| **3-agent pipeline** | Three-pass LLM execution per stage: Primary (generate) → Specialist (validate & enrich) → Reviewer (13-point quality checklist). Enabled by `multi_agent=True` (default). |
| **Primary Agent** | The first agent in the pipeline that generates initial content using the stage's `system_prompt` persona |
| **Specialist Agent** | The second agent that validates, enriches, and adds domain-specific depth using `specialist_system_prompt` |
| **Reviewer Agent** | The third agent that applies the 13-point quality checklist via `review_system_prompt` |
| **`get_phase_models()`** | Function in `agent_teams.py` returning `{"primary": model, "specialist": model, "reviewer": model}` resolved from `WorkflowConfig` |
| **`_run_specialist()`** | Method in `RfpPhaseBase` that runs the specialist agent with full token safety (chunking + dynamic capping) |
| **RfpPhaseBase** | Abstract base class for all RFP phases; implements the 3-agent execution engine with token safety at every call |
| **RfpPhaseConfig** | Dataclass holding model, temperature, max_tokens, n_reviews, review_model, multi_agent, specialist_model |
| **PhaseContext** | Carries `task`, `work_dir`, `shared_state`, and `output_data` through phase execution |
| **PhaseResult** | Return value from `phase.execute()` — status, context, timing, optional error |
| **Shared State** | Cumulative dictionary carrying context between stages (`output_data["shared"]`) |
| **RFP** | Request for Proposal — a document requesting vendors to submit proposals for a project |
| **TaskStage** | Database model tracking individual stage status and output |
| **WorkflowRun** | Database model for the parent task record |
| **Session** | Database record grouping all runs/stages/costs under one workspace |
| **_ConsoleCapture** | Thread-safe stdout/stderr interceptor for real-time streaming |
| **HITL** | Human-in-the-loop — allowing human review/edit between AI stages |
| **CostRepository** | Tracks per-LLM-call costs and aggregates them per task |
| **TaskStageRepository** | CRUD operations for stage records in the database |
| **SessionManager** | Service for creating and managing sessions |
| **Stepper** | UI component showing the 8-step wizard progress indicator |
| **RefinementChat** | AI-powered chat sidebar for iterative content improvement |
| **Split-View Editor** | 60% markdown editor/preview + 40% refinement chat layout |
| **Token capacity management** | System that prevents context window overflow at every LLM call via dynamic capping, prompt chunking, and 0.75 safety margin |
| **Safety margin (0.75)** | Fraction of model context window used for budget calculation — accounts for tiktoken undercounting by 10–20% |
| **Dynamic currency** | Currency code and symbol extracted from the RFP at Stage 1, propagated to all cost-producing stages |
| **Divide-and-accumulate** | Stage 7 strategy: divide sources into groups → generate partial proposals → merge with accumulation pass (zero data loss) |
| **`group_sources_by_budget`** | Greedy bin-packing of source sections into groups that fit the model's context window |
| **`chunk_prompt_if_needed`** | Splits oversized prompts at `---` section boundaries into sub-prompts that fit the context window |
| **`_single_generate`** | Stage 7 helper that fires one LLM call with dynamic `max_completion_tokens` capping |
| **ADR** | Architecture Decision Record — structured record of a key architectural decision |
| **RPO/RTO** | Recovery Point Objective / Recovery Time Objective — disaster recovery metrics |

---

## 11. Complete Flow Explanation — Classes, Functions & Agents

This section provides an exhaustive trace of every class, function, database model, and phase involved in the RFP Proposal Generator.

---

### 11.1 End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MARS UI (Next.js)                            │
│                                                                     │
│  TaskList.tsx                                                       │
│    └── click "RFP Proposal Generator"                               │
│         └──► RfpProposalTask.tsx  (8-step wizard container)         │
│              ├── Stepper (visual progress bar, clickable)            │
│              ├── Step 0: RfpSetupPanel.tsx                           │
│              │    ├── FileUploadZone → upload docs (PDF auto-extract)│
│              │    ├── textarea → RFP content                        │
│              │    ├── textarea → additional context                  │
│              │    └── "Analyze Requirements" button                  │
│              ├── Steps 1-6: RfpReviewPanel.tsx (×6 instances)        │
│              │    ├── Markdown editor / preview toggle               │
│              │    ├── RefinementChat sidebar (AI-assisted editing)   │
│              │    ├── Auto-save with debounce                        │
│              │    └── "Next" → auto-triggers next phase execution    │
│              └── Step 7: RfpProposalPanel.tsx                        │
│                   ├── Compiled proposal preview                     │
│                   └── Download artifacts (7 .md files)              │
│                                                                     │
│  useRfpTask.ts (React hook — manages all state)                     │
│    ├── createTask()    → POST /api/rfp/create                       │
│    ├── executeStage()  → POST /api/rfp/{id}/stages/{n}/execute      │
│    ├── fetchContent()  → GET  /api/rfp/{id}/stages/{n}/content      │
│    ├── saveContent()   → PUT  /api/rfp/{id}/stages/{n}/content      │
│    ├── refineContent() → POST /api/rfp/{id}/stages/{n}/refine       │
│    ├── resetFromStage()→ POST /api/rfp/{id}/reset-from/{n}          │
│    ├── connectWs()     → ws://host/ws/rfp/{id}/{n}                  │
│    ├── startPolling()  → GET  /api/rfp/{id} (every 5s)              │
│    └── startConsolePoll() → GET /api/rfp/{id}/stages/{n}/console    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Python)                         │
│                                                                     │
│  backend/routers/rfp.py                                             │
│    ├── create_rfp_task()      → SessionManager.create_session()     │
│    │                          → WorkflowRun (DB)                    │
│    │                          → TaskStageRepository.create_stage()×7│
│    ├── execute_rfp_stage()    → build_shared_state()                │
│    │                          → _build_rfp_context()                │
│    │                          → asyncio.create_task(_run_rfp_stage) │
│    ├── _run_rfp_stage()       → _load_phase_class(N)               │
│    │                          → PhaseClass(config=RfpPhaseConfig)   │
│    │                          → PhaseContext(task, shared_state)     │
│    │                          → await phase.execute(ctx)            │
│    │                            ├── generation pass (LLM call 1)    │
│    │                            └── review pass (LLM call 2)        │
│    │                          → CostRepository.record_cost()        │
│    │                          → TaskStageRepository.update_status()  │
│    │                          → write .md file to disk               │
│    ├── refine_rfp_content()   → create_openai_client()              │
│    │                          → asyncio.to_thread(refinement call)  │
│    └── reset_from_stage()     → reset to pending, delete files      │
│                                                                     │
│  backend/main.py                                                    │
│    └── rfp_websocket_endpoint()                                     │
│         → polls _console_buffers → sends stage_completed/failed     │
│                                                                     │
│  cmbagent/phases/rfp/base.py — RfpPhaseBase                        │
│    └── execute(ctx) → generation pass + review pass(es)             │
│         ├── create_openai_client() → OpenAI | AzureOpenAI           │
│         ├── resolve_model_for_provider() → deployment name          │
│         ├── _gen() → client.chat.completions.create(...)            │
│         ├── _review(draft) → client.chat.completions.create(...)    │
│         └── PhaseResult(status, context, timing)                    │
│                                                                     │
│  cmbagent/database/                                                 │
│    ├── models.py   → WorkflowRun, TaskStage, CostRecord, Session    │
│    ├── repository.py → TaskStageRepository, CostRepository          │
│    └── base.py     → init_database(), get_db_session()              │
│                                                                     │
│  backend/services/                                                  │
│    ├── session_manager.py → SessionManager.create_session()         │
│    └── pdf_extractor.py → extract_pdf_content() (text+tables+images)│
└─────────────────────────────────────────────────────────────────────┘
```

---

### 11.2 All Classes Used

#### 11.2.1 Phase Classes (`cmbagent/phases/rfp/`)

| Class | File | Purpose |
|---|---|---|
| **`RfpPhaseConfig`** | `base.py` | Dataclass: model, temperature, max_tokens, n_reviews, review_model |
| **`RfpPhaseBase`** | `base.py` | Abstract base — generate→review execution engine |
| **`RfpRequirementsPhase`** | `requirements_phase.py` | Stage 1: Business analysis persona, requirements extraction |
| **`RfpToolsPhase`** | `tools_phase.py` | Stage 2: Solutions architect persona, tool comparison tables |
| **`RfpCloudPhase`** | `cloud_phase.py` | Stage 3: Cloud architect persona, provider comparison |
| **`RfpImplementationPhase`** | `implementation_phase.py` | Stage 4: PM persona, timeline and sprint planning |
| **`RfpArchitecturePhase`** | `architecture_phase.py` | Stage 5: System architect persona, ADRs |
| **`RfpExecutionPhase`** | `execution_phase.py` | Stage 6: Delivery exec persona, go-live strategy |
| **`RfpProposalPhase`** | `proposal_phase.py` | Stage 7: Proposal writer persona, divide-and-accumulate compilation |

#### 11.2.1b Token Utilities (`cmbagent/phases/rfp/token_utils.py`)

| Function | Purpose |
|---|---|
| **`_default_model()`** | Resolves the default model from `WorkflowConfig` (used as fallback for token counting functions) |
| **`get_model_limits(model)`** | Returns `(max_context, max_output)` for a model; prefix match + fallback |
| **`count_tokens(text, model)`** | Token count via tiktoken (fallback: chars÷4). Model defaults to `_default_model()` if not provided |
| **`count_messages_tokens(messages, model)`** | Token count for chat message lists. Model defaults to `_default_model()` if not provided |
| **`chunk_prompt_if_needed(...)`** | Returns `None` (fits) or `List[str]` (chunks split at `---` boundaries) |
| **`group_sources_by_budget(...)`** | Greedy bin-packing of source keys into context-fitting batches |

#### 11.2.2 Backend Classes

| Class | File | Purpose |
|---|---|---|
| **`APIRouter`** | `fastapi` | Defines all `/api/rfp/*` REST endpoints |
| **`_ConsoleCapture`** | `routers/rfp.py` | Thread-safe stdout/stderr interceptor for real-time streaming |
| **`RfpCreateRequest`** | `models/rfp_schemas.py` | Pydantic model: `task`, `rfp_context`, `config`, `work_dir` |
| **`RfpExecuteRequest`** | `models/rfp_schemas.py` | Pydantic model: `config_overrides` |
| **`RfpContentUpdateRequest`** | `models/rfp_schemas.py` | Pydantic model: `content`, `field` |
| **`RfpRefineRequest`** | `models/rfp_schemas.py` | Pydantic model: `message`, `content` |
| **`RfpStageResponse`** | `models/rfp_schemas.py` | Stage info: number, name, status, timestamps, error |
| **`RfpCreateResponse`** | `models/rfp_schemas.py` | `task_id`, `work_dir`, `stages[]` |
| **`RfpStageContentResponse`** | `models/rfp_schemas.py` | Stage content: `content`, `shared_state`, `output_files` |
| **`RfpRefineResponse`** | `models/rfp_schemas.py` | `refined_content`, `message` |
| **`RfpTaskStateResponse`** | `models/rfp_schemas.py` | Full state: `stages[]`, `progress_percent`, `total_cost_usd` |
| **`RfpRecentTaskResponse`** | `models/rfp_schemas.py` | Resume flow: `task_id`, `task`, `status`, `current_stage` |

#### 11.2.3 Database Models (SQLAlchemy ORM)

| Model | File | Purpose | Key Columns |
|---|---|---|---|
| **`Session`** | `cmbagent/database/models.py` | Groups all runs/stages/costs | `id`, `name`, `status`, `created_at` |
| **`WorkflowRun`** | `cmbagent/database/models.py` | Parent task record | `id`, `session_id`, mode=`"rfp-proposal"`, agent=`"phase_orchestrator"`, `task_description`, `meta` |
| **`TaskStage`** | `cmbagent/database/models.py` | Per-stage tracking (×7) | `id`, `parent_run_id`, `stage_number`, `stage_name`, `status`, `output_data`, `error_message` |
| **`CostRecord`** | `cmbagent/database/models.py` | Per-LLM-call cost | `parent_run_id`, `model`, `prompt_tokens`, `completion_tokens`, `cost_usd` |

#### 11.2.4 Repository Classes

| Repository | Methods Used by RFP |
|---|---|
| **`TaskStageRepository`** | `create_stage()`, `list_stages()`, `update_stage_status()`, `get_task_progress()` |
| **`CostRepository`** | `record_cost()`, `get_task_total_cost()` |

#### 11.2.5 Service Classes

| Service | File | Methods |
|---|---|---|
| **`SessionManager`** | `backend/services/session_manager.py` | `create_session(mode, config, name)` |
| **`pdf_extractor`** | `backend/services/pdf_extractor.py` | `extract_pdf_content(path)` — text, tables, images |
| **`LLMProviderConfig`** | `cmbagent/llm_provider.py` | Auto-detects Azure vs OpenAI; `create_openai_client()`, `resolve_model_for_provider()` |

#### 11.2.6 Frontend Components

| Component | File | Purpose |
|---|---|---|
| **`RfpProposalTask`** | `components/tasks/RfpProposalTask.tsx` | 8-step wizard container with Stepper navigation |
| **`RfpSetupPanel`** | `components/rfp/RfpSetupPanel.tsx` | Step 0: file upload, RFP text, context, submit |
| **`RfpReviewPanel`** | `components/rfp/RfpReviewPanel.tsx` | Steps 1–6: split-view editor + refinement chat |
| **`RfpExecutionPanel`** | `components/rfp/RfpExecutionPanel.tsx` | Stage execution progress with timer and cost |
| **`RfpProposalPanel`** | `components/rfp/RfpProposalPanel.tsx` | Step 7: proposal preview + download artifacts |
| **`RefinementChat`** | `components/deepresearch/RefinementChat.tsx` | Chat sidebar for AI-powered content improvement |
| **`ExecutionProgress`** | `components/deepresearch/ExecutionProgress.tsx` | Scrolling console output display |
| **`FileUploadZone`** | `components/deepresearch/FileUploadZone.tsx` | Drag-and-drop upload with status indicators |

#### 11.2.7 Frontend Hook & Types

| Item | File | Purpose |
|---|---|---|
| **`useRfpTask()`** | `hooks/useRfpTask.ts` | Central state management — all state + 12 action functions |
| **`RfpTaskState`** | `types/rfp.ts` | TypeScript type for task state |
| **`RfpWizardStep`** | `types/rfp.ts` | Union type: `0 \| 1 \| 2 \| ... \| 7` |
| **`RFP_STEP_LABELS`** | `types/rfp.ts` | Human labels: Setup, Requirements, Tools & Tech, … |
| **`RFP_AVAILABLE_MODELS`** | `types/rfp.ts` | 9 model options for stage config |

---

### 11.3 All Functions Used (Mapped by Operation)

#### 11.3.1 Backend Helper Functions (`backend/routers/rfp.py`)

| Function | Signature | Purpose |
|---|---|---|
| `_get_db()` | `() → Session` | Initialize database (once) + return new DB session |
| `_get_stage_repo()` | `(db, session_id) → TaskStageRepository` | Create session-scoped stage repository |
| `_get_cost_repo()` | `(db, session_id) → CostRepository` | Create session-scoped cost repository |
| `_get_work_dir()` | `(task_id, session_id, base_work_dir) → str` | Compute filesystem path |
| `_get_session_id_for_task()` | `(task_id, db) → str` | Look up session_id from WorkflowRun |
| `build_shared_state()` | `(task_id, up_to_stage, db, session_id) → Dict` | Merge `output_data["shared"]` from all completed prior stages |
| `_stage_to_response()` | `(stage) → RfpStageResponse` | Convert ORM TaskStage to Pydantic response |
| `_build_rfp_context()` | `(work_dir) → str` | Read uploaded files, extract PDF text (PyMuPDF), preview text files (4KB), escape braces |
| `_get_console_lines()` | `(buf_key, since_index) → List[str]` | Thread-safe read from `_console_buffers` |
| `_clear_console_buffer()` | `(buf_key) → None` | Remove buffer entry after stage completes |
| `_load_phase_class()` | `(stage_num) → type` | Dynamic `importlib` import of phase class |

#### 11.3.2 Backend Route Handlers (`backend/routers/rfp.py`)

| Endpoint | Function | What It Does |
|---|---|---|
| `POST /api/rfp/create` | `create_rfp_task()` | 1. `SessionManager.create_session()`; 2. `os.makedirs(work_dir)`; 3. Write `rfp_input.md` + `rfp_context.md`; 4. Create `WorkflowRun` (agent=`"phase_orchestrator"`); 5. `create_stage()` ×7; 6. Return task_id |
| `PATCH /{id}/description` | `update_rfp_task_description()` | Update `task_description` + `meta.rfp_context`; rewrite disk files |
| `GET /recent` | `get_recent_rfp_tasks()` | List up to 10 executing `rfp-proposal` runs with progress |
| `GET /{id}` | `get_rfp_task_state()` | Full state: 7 stages, progress %, total cost, current stage |
| `POST /{id}/stages/{N}/execute` | `execute_rfp_stage()` | Validate prior stages → mark running → `build_shared_state()` → `asyncio.create_task(_run_rfp_stage)` |
| `GET /{id}/stages/{N}/content` | `get_rfp_stage_content()` | Return from `output_data["shared"]`, fallback to .md file |
| `PUT /{id}/stages/{N}/content` | `update_rfp_stage_content()` | Save edits to DB `output_data["shared"]` + write .md file |
| `POST /{id}/stages/{N}/refine` | `refine_rfp_content()` | LLM call with token capacity check, dynamic cap, content trimming if overflow, `timeout=300` |
| `GET /{id}/stages/{N}/console` | `get_rfp_console()` | Return new console lines since `since` index |
| `POST /{id}/reset-from/{N}` | `reset_from_stage()` | Reset stages ≥ N to pending; delete .md files |
| `GET /{id}/download/{file}` | `download_rfp_artifact()` | Validate filename → FileResponse with attachment header |
| `DELETE /{id}` | `delete_rfp_task()` | `shutil.rmtree(work_dir)` + delete WorkflowRun (cascade) |

#### 11.3.3 Stage Execution Engine (`_run_rfp_stage`)

| Step | Action | Details |
|---|---|---|
| 1 | Set up console capture | `_ConsoleCapture(buf_key, sys.stdout)` → replaces stdout/stderr |
| 2 | Load phase class | `_load_phase_class(stage_num)` → dynamic importlib |
| 3 | Instantiate phase | `PhaseClass(config=PhaseClass.config_class(model, n_reviews))` |
| 4 | Build PhaseContext | `PhaseContext(workflow_id, task, work_dir, shared_state)` |
| 5 | Execute phase | `await phase.execute(ctx)` → generate → review cycle |
| 6 | Extract content | `result.context.output_data["shared"][shared_key]` |
| 7 | Track cost | `CostRepository.record_cost(parent_run_id, model, tokens, cost_usd)` |
| 8 | Save output file | Write to `{work_dir}/input_files/{filename}` |
| 9 | Update DB | `TaskStageRepository.update_stage_status("completed", output_data)` |
| 10 | Restore stdout | `sys.stdout = old_stdout; sys.stderr = old_stderr` |
| (error) | Mark failed | `update_stage_status("failed", error_message)` |

#### 11.3.4 Phase Execution Engine (`RfpPhaseBase.execute`)

| Step | Action | Details |
|---|---|---|
| 1 | Create LLM client | `create_openai_client(timeout=300)` → OpenAI or AzureOpenAI |
| 2 | Resolve model | `resolve_model_for_provider(model)` → Azure deployment name if needed |
| 3 | Build user prompt | `self.build_user_prompt(context)` → includes RFP + shared_state |
| 4 | Token capacity check | `chunk_prompt_if_needed(safety_margin=0.75)` → `None` (fits) or `List[str]` (chunks) |
| 5 | Generation pass | Single: dynamic `max_completion_tokens` cap → API call. Chunked: per-chunk calls with context instructions, each dynamically capped |
| 6 | Empty content guard | Reject if `len(content) < 100` chars — abort with error |
| 7 | Review pass(es) | Token check + chunking for review. Single: dynamic cap. Chunked: per-chunk dynamic caps. Only accepted if review output > 30% of draft length |
| 8 | Save to disk | Write to `{work_dir}/input_files/{output_filename}` |
| 9 | Build output | `context.output_data = { "shared": {...}, "artifacts": {...}, "cost": {...} }` |
| 10 | Return result | `PhaseResult(status=COMPLETED, context=context, timing={...})` |

#### 11.3.5 WebSocket Handler (`backend/main.py`)

| Function | What It Does |
|---|---|
| `rfp_websocket_endpoint(ws, task_id, stage_num)` | Accept connection → poll `_get_console_lines()` every 1s → send console events → check stage status → send `stage_completed`/`stage_failed` → cleanup |

#### 11.3.6 Frontend Hook Functions (`useRfpTask.ts`)

| Function | API Call | What It Does |
|---|---|---|
| `createTask(task, ctx, config)` | `POST /api/rfp/create` | Create task; if auto-created, PATCH description |
| `autoCreateTask()` | `POST /api/rfp/create` | Create empty task for file uploads |
| `executeStage(N, id?)` | `POST .../execute` | Trigger phase execution; start WS + polling + console |
| `fetchStageContent(N)` | `GET .../content` | Load output into `editableContent` state |
| `saveStageContent(N, content, field)` | `PUT .../content` | Save edits to DB + disk |
| `refineContent(N, message, content)` | `POST .../refine` | Send refinement instruction to LLM |
| `uploadFile(file)` | `POST /api/files/upload` | Auto-create task if needed; upload file |
| `loadTaskState(id)` | `GET /api/rfp/{id}` | Fetch full task state |
| `resumeTask(id)` | `GET /api/rfp/{id}` | Load state + determine resume step + reconnect WS |
| `resetFromStage(N)` | `POST .../reset-from/{N}` | Reset later stages; reload state |
| `deleteTask()` | `DELETE /api/rfp/{id}` | Delete task; reset local state |
| `connectWs(id, N)` | WS `/ws/rfp/{id}/{N}` | Listen for `stage_completed`/`stage_failed` |
| `startPolling(id, N)` | `GET /api/rfp/{id}` every 5s | Fallback polling |
| `startConsolePoll(id, N)` | `GET .../console` every 2s | Append console lines to state |

---

### 11.4 Orchestration Type: Phase-Based Generate → Review

The RFP Proposal Generator uses a **custom phase-based** execution model:

```
┌──────────────────────────────────────────────────────────────────────┐
│              MARS ORCHESTRATION MODELS                                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────┐             │
│  │  1. SwarmOrchestrator (Multi-Agent)                 │             │
│  │     Used by: Copilot, Planning & Control (swarm)    │             │
│  │     Agents hand off work dynamically                │             │
│  └─────────────────────────────────────────────────────┘             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────┐             │
│  │  2. PhaseOrchestrator (Sequential)                  │             │
│  │     Used by: Deep Research, Planning & Control      │             │
│  │     Phases from PhaseRegistry, each invokes agents  │             │
│  └─────────────────────────────────────────────────────┘             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────┐  ◄── RFP   │
│  │  3. Phase-Based Generate → Review (Custom)          │             │
│  │     Used by: RFP Proposal Generator                 │             │
│  │                                                     │             │
│  │  7 RfpPhaseBase subclasses loaded dynamically       │             │
│  │  via _load_phase_class() using importlib.           │             │
│  │                                                     │             │
│  │  Each phase (multi_agent=True):                     │             │
│  │    ├── Primary pass (expert persona prompt)         │             │
│  │    ├── Specialist pass (domain validation)          │             │
│  │    └── Reviewer pass (13-point quality checklist)   │             │
│  │                                                     │             │
│  │  No CMBAgent instantiation. No GroupChat.           │             │
│  │  No tool-calling. Pure prompt → markdown.           │             │
│  │                                                     │             │
│  │  LLM calls per stage: 3 (primary + specialist + review) │        │
│  │  Total LLM calls:     21 (7 stages × 3)            │             │
│  │  + Human review between every stage                 │             │
│  └─────────────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
```

### 11.5 LLM Call Sites

There are **11 protected LLM call sites** in the RFP workflow (with `multi_agent=True`). Every call has dynamic `max_completion_tokens` capping and automatic prompt chunking with a 0.75 safety margin:

| # | Call Site | Location | Purpose | Token Protection |
|---|-----------|----------|---------|-----------------|
| 1 | **Generation (single)** | `RfpPhaseBase.execute()` | Primary agent generates stage content | `chunk_prompt_if_needed` + dynamic cap |
| 2 | **Generation (chunked)** | `RfpPhaseBase.execute()` | Primary agent when prompt exceeds context | Per-chunk dynamic cap |
| 3 | **Specialist (single)** | `RfpPhaseBase._run_specialist()` | Specialist agent validates & enriches | `chunk_prompt_if_needed` + dynamic cap |
| 4 | **Specialist (chunked)** | `RfpPhaseBase._run_specialist()` | Specialist agent when content exceeds context | Per-chunk dynamic cap |
| 5 | **Review (single)** | `RfpPhaseBase.execute()` | Reviewer agent 13-point checklist | `chunk_prompt_if_needed` + dynamic cap |
| 6 | **Review (chunked)** | `RfpPhaseBase.execute()` | Reviewer when draft exceeds context | Per-chunk dynamic cap |
| 7 | **Stage 7 generation** | `RfpProposalPhase._single_generate()` | Single/partial/accumulation calls | Dynamic cap via `get_model_limits` |
| 8 | **Stage 7 specialist** | `RfpProposalPhase.execute()` | Specialist validates compiled proposal | `_run_specialist()` (inherited) |
| 9 | **Stage 7 review (single)** | `RfpProposalPhase.execute()` | Review compiled proposal | `chunk_prompt_if_needed` + dynamic cap |
| 10 | **Stage 7 review (chunked)** | `RfpProposalPhase.execute()` | Chunked review of large proposal | Per-chunk dynamic cap |
| 11 | **Refinement chat** | `refine_rfp_content()` in `rfp.py` | User-requested content improvement | Dynamic cap + content trimming |

All LLM calls use: `temperature=0.7`, `max_completion_tokens=dynamically capped` (default ceiling: `16384`).
Models are assigned dynamically from `WorkflowConfig.default_llm_model` via `get_phase_models()` when `multi_agent=True` (see [Section 15.2](#152-model-assignments)).

### 11.6 Cost & Performance Profile (7-Stage RFP Task)

```
┌──────────────────────────────────────────────────────────────────────┐
│              Phase-Based Generate → Review (Current RFP)              │
│──────────────────────────────────────────────────────────────────────│
│                                                                      │
│  Stage 1        Stage 2        Stage 3        ...     Stage 7        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          ┌──────────┐    │
│  │Primary   │  │Primary   │  │Primary   │          │Primary   │    │
│  │ (LLM 1)  │  │ (LLM 1)  │  │ (LLM 1)  │          │ (LLM 1)  │    │
│  ├──────────┤  ├──────────┤  ├──────────┤          ├──────────┤    │
│  │Specialist│  │Specialist│  │Specialist│          │Specialist│    │
│  │ (LLM 2)  │  │ (LLM 2)  │  │ (LLM 2)  │          │ (LLM 2)  │    │
│  ├──────────┤  ├──────────┤  ├──────────┤          ├──────────┤    │
│  │Reviewer  │  │Reviewer  │  │Reviewer  │          │Reviewer  │    │
│  │ (LLM 3)  │  │ (LLM 3)  │  │ (LLM 3)  │          │ (LLM 3)  │    │
│  └──┬───────┘  └──┬───────┘  └──┬───────┘          └──┬───────┘    │
│     │ Human       │ Human       │ Human               │             │
│     │ Review      │ Review      │ Review              │             │
│     ▼             ▼             ▼                     ▼             │
│  ~80s           ~80s          ~90s                 ~120s            │
│                                                                      │
│  Total LLM calls:  21 (7 stages × 3 agents)                        │
│  Total time:       ~8-12 minutes (plus user review time)            │
│  Init overhead:    0 seconds (no agent initialization)              │
│  Quality:          Highest (specialist validation + reviewer)       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 12. Token Capacity Management

Source: `cmbagent/phases/rfp/token_utils.py`, `cmbagent/phases/rfp/base.py`, `cmbagent/phases/rfp/proposal_phase.py`, `backend/routers/rfp.py`

### 12.1 Overview

Every LLM call in the RFP pipeline is protected against context window overflow. There are **11 distinct LLM call sites** (with `multi_agent=True`), each with:
- **Dynamic `max_completion_tokens` capping** — prompt + output never exceeds context
- **Automatic prompt chunking** — oversized prompts are split at `---` section boundaries
- **0.75 safety margin** — tiktoken undercounts by 10–20% vs the API's actual tokenizer

### 12.2 Safety Margin

All token budget calculations use:

```python
usable_ctx = int(max_ctx * 0.75) - max_completion_tokens
```

The 0.75 margin (instead of 0.90) accounts for tiktoken's undercounting of special tokens, markdown formatting characters, and Unicode content.

### 12.3 Dynamic `max_completion_tokens` Capping

At every LLM call:

```python
prompt_tokens = count_tokens(system + user, model)
available_for_output = max_ctx - prompt_tokens - 200  # safety buffer
max_comp = min(config.max_completion_tokens, max(available_for_output, 4096))
```

This prevents `finish_reason=length` truncation by ensuring the model has room for output.

### 12.4 Prompt Chunking

When a prompt exceeds the usable context window:
1. The user prompt is split at `---` section boundaries
2. Each chunk is sent as a separate API call with context about which part it is
3. Results are concatenated

If no `---` boundaries exist, the prompt is returned as a single-element list so the caller processes it through the chunked code path (with logging) rather than silently sending an oversized request.

### 12.5 Protected Call Sites

| # | Call Site | File | Protection |
|---|-----------|------|------------|
| 1 | Generation (single-shot) | `base.py` | `chunk_prompt_if_needed` + dynamic cap |
| 2 | Generation (chunked) | `base.py` | Per-chunk dynamic cap |
| 3 | Review (single-shot) | `base.py` | `chunk_prompt_if_needed` + dynamic cap |
| 4 | Review (chunked) | `base.py` | Per-chunk dynamic cap |
| 5 | Stage 7 `_single_generate` | `proposal_phase.py` | Dynamic cap via `get_model_limits` |
| 6 | Stage 7 review (single) | `proposal_phase.py` | `chunk_prompt_if_needed` + dynamic cap |
| 7 | Stage 7 review (chunked) | `proposal_phase.py` | Per-chunk dynamic cap |
| 8 | Refinement chat | `rfp.py` | Dynamic cap + content trimming (start+end) |

### 12.6 Key Functions (`token_utils.py`)

| Function | Purpose |
|----------|---------|
| `get_model_limits(model)` | Returns `(max_context, max_output)` for a model |
| `count_tokens(text, model)` | Count tokens using tiktoken (fallback: chars÷4) |
| `count_messages_tokens(messages, model)` | Count tokens for a chat message list |
| `chunk_prompt_if_needed(system, user, model, max_completion, safety_margin)` | Returns `None` (fits) or `List[str]` (chunks) |
| `group_sources_by_budget(sources, base_tokens, model, max_completion, safety_margin)` | Group source keys into batches that fit context window |

### 12.7 Model Token Limits Registry

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

---

## 13. Dynamic Currency System

Source: `cmbagent/phases/rfp/requirements_phase.py` (extraction), `cmbagent/phases/rfp/base.py` (rule generation + automatic injection)

### 13.1 Currency Extraction (Stage 1)

The requirements phase prompt includes:

```
10. **Currency** — Identify the currency used in the RFP (e.g., USD, EUR, GBP, INR, AUD, CAD).
    Look for currency symbols ($, €, £, ₹), currency codes, or country context.
    Search the ENTIRE RFP including payment terms, billing clauses, and annexures.
    Output:
    ## Currency
    **Primary Currency:** <CODE> (<SYMBOL>)
    If no currency is explicitly stated, default to USD ($).
```

### 13.2 Currency Rule Generation (`get_currency_rule`) — 3-Pass Detection

`RfpPhaseBase.get_currency_rule(context)` uses a robust **3-pass detection** system:

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

### 13.3 Automatic Currency Injection (Base Class Level)

The currency rule is **automatically injected** by `RfpPhaseBase` at 3 points — no individual phase can miss it:

| Agent | Injection Point | Code Location |
|-------|----------------|---------------|
| **Primary Agent** | Appended to `build_user_prompt()` output | `execute()` in `base.py` |
| **Specialist Agent** | Appended to specialist validation prompt | `_run_specialist()` in `base.py` |
| **Reviewer Agent** | Appended to review prompt | Review loop in `execute()` |

This means **all 7 stages × all 3 agents** (21 LLM calls) enforce the correct currency.

Additionally, individual phases (Tools, Cloud, Implementation, Proposal) include the currency rule explicitly in their `build_user_prompt()` — this is redundant but harmless (the rule is simply reinforced).

The review system prompt also uses generic "single consistent currency" language (item 9) so it validates any detected currency.

---

## 14. Divide-and-Accumulate Strategy (Stage 7)

Source: `cmbagent/phases/rfp/proposal_phase.py`

### 14.1 Problem

Stage 7 injects all 6 prior stage outputs into one prompt. For GPT-4o (128K context), this frequently exceeds the context window. Truncation or condensation would lose critical cost figures, comparison tables, and timelines.

### 14.2 Solution: Zero-Data-Loss

`RfpProposalPhase` overrides `execute()` with a custom strategy:

**PATH A (prompt fits):**
1. Build full prompt with all 6 sources
2. Single generation call with dynamic `max_completion_tokens` cap
3. If API returns empty/short output (tiktoken undercount) → automatically fall back to PATH B

**PATH B (prompt overflows or PATH A failed):**
1. `group_sources_by_budget()` — greedy bin-packing of sources into groups that each fit the context window
2. For each group: `_build_partial_prompt()` targeting only that group's assigned proposal sections → `_single_generate()` with dynamic cap
3. Accumulation pass: LLM merges all partial outputs into one cohesive document (preserves 100% of content, fixes numbering, removes duplicates)
4. If accumulation prompt itself overflows → direct concatenation (still zero data loss)

**Specialist pass** (when `multi_agent=True`):
- Runs after PATH A/B content generation, before review
- Uses `_run_specialist()` inherited from `RfpPhaseBase`
- Full token safety: `chunk_prompt_if_needed(safety_margin=0.75)` + dynamic cap
- Accepted if enriched output > 30% of original length

**Review pass:**
- Uses `chunk_prompt_if_needed(safety_margin=0.75)` on the compiled proposal
- Single-shot or chunked review with dynamic `max_completion_tokens` cap at every call
- Only accepted if review output > 50% of draft length

### 14.3 Source-to-Section Mapping

| Source | Assigned Proposal Sections |
|--------|---------------------------|
| `requirements_analysis` | Cover Page, Executive Summary, Purpose & Introduction, Understanding of Requirements |
| `tools_technology` | Technology Stack & Tooling, Appendix B (Evaluation Matrices) |
| `cloud_infrastructure` | Cloud Infrastructure & Provider Selection, Appendix A (Cost Breakdowns) |
| `implementation_plan` | Methodology, Timeline & Milestones, Resources, Implementation Approach |
| `architecture_design` | Proposed Solution Overview, System Architecture, Appendix C (Charts & Data) |
| `execution_strategy` | Execution Plan, Risk Management, Qualifications, Compliance, Pricing, Terms, Appendices D & E |

### 14.4 Key Helper (`_single_generate`)

All generation calls in Stage 7 go through `_single_generate()` which:
1. Calculates prompt tokens via `count_tokens()`
2. Dynamically caps `max_completion_tokens` to stay within context
3. Stores `_last_usage` and `_last_finish_reason` for diagnostics

---

## 15. Multi-Agent System

Source: `cmbagent/phases/rfp/agent_teams.py`, `cmbagent/phases/rfp/base.py`

### 15.1 Overview

Each RFP stage uses a **team of 3 specialised agents** that collaborate sequentially:

```
Primary Agent → Specialist Agent → Reviewer Agent
  (generate)       (validate)        (quality check)
```

- **Primary Agent** — Domain expert that generates the initial content (same persona as the stage's `system_prompt`)
- **Specialist Agent** — Secondary expert that validates, enriches, and adds domain-specific depth using a dedicated `specialist_system_prompt`
- **Reviewer Agent** — Quality reviewer with 13-point checklist (existing `review_system_prompt`)

### 15.2 Model Assignments

All agent roles across all stages use the **same model**, resolved dynamically from `WorkflowConfig.default_llm_model`. No per-stage differentiation — the model is configured once and applied everywhere:

| Stage | Primary Model | Specialist Model | Reviewer Model |
|-------|--------------|-----------------|----------------|
| 1 — Requirements | (config) | (config) | (config) |
| 2 — Tools & Technology | (config) | (config) | (config) |
| 3 — Cloud Infrastructure | (config) | (config) | (config) |
| 4 — Implementation | (config) | (config) | (config) |
| 5 — Architecture Design | (config) | (config) | (config) |
| 6 — Execution Strategy | (config) | (config) | (config) |
| 7 — Proposal Compilation | (config) | (config) | (config) |

> **(config)** = `WorkflowConfig.default_llm_model` (e.g., `gpt-4o`). Change in one place → changes everywhere.

### 15.3 Specialist Roles Per Stage

| Stage | Specialist Role | Key Validation Focus |
|-------|----------------|---------------------|
| 1 | Domain Validation Expert | Implicit requirements, stakeholder gaps, hidden costs, currency |
| 2 | Security & Compliance Auditor | CVE accuracy, license compliance, supply chain risks |
| 3 | Cloud Cost Optimisation Specialist | Pricing accuracy, reserved vs on-demand, FinOps |
| 4 | Delivery Assurance Analyst | Timeline feasibility, resource bottlenecks, sprint velocity |
| 5 | Scalability & Implementation Engineer | Component boundaries, performance bottlenecks, ADR quality |
| 6 | Risk & Governance Specialist | Go-live strategy, risk register, RACI, KPIs |
| 7 | Senior Proposal Editor | Document flow, cost table math, placeholder detection |

### 15.4 Execution Flow

```
┌─ execute() ─────────────────────────────────────────────────┐
│  1. Resolve models from get_phase_models()                  │
│  2. Primary Agent generates content (system_prompt)         │
│     └─ Token safety: chunk_prompt_if_needed + dynamic cap   │
│  3. Specialist Agent validates & enriches                   │
│     └─ _run_specialist(): full token safety (0.75 margin)   │
│     └─ Accept if enriched > 30% of original length          │
│  4. Reviewer Agent quality-checks (review_system_prompt)    │
│     └─ Token safety: chunk_prompt_if_needed + dynamic cap   │
│     └─ Accept if reviewed > 30% of draft length             │
│  5. Save to disk + return PhaseResult                       │
└─────────────────────────────────────────────────────────────┘
```

### 15.5 Configuration

```python
RfpPhaseConfig(
    multi_agent=True,          # Enable 3-agent pipeline (default: True)
    specialist_model=None,     # Override specialist model (default: per-stage)
    # ... existing fields ...
)
```

Set `multi_agent=False` to revert to the original 2-pass (generate → review) behaviour.

### 15.6 Token Safety

The specialist pass has the same full token protection as all other LLM calls:

1. `chunk_prompt_if_needed(safety_margin=0.75)` — split if prompt exceeds usable context
2. Dynamic `max_completion_tokens` capping — `min(config.max_completion_tokens, max(available, 4096))`
3. Chunked specialist — each chunk independently capped
4. Content validation — enriched output must exceed 30% of original to be accepted

### 15.7 Files

| File | Purpose |
|------|---------|
| `agent_teams.py` | `_build_phase_models()` function, `get_phase_models()` helper |
| `base.py` | `RfpPhaseConfig.multi_agent`, `specialist_system_prompt` property, `_run_specialist()` method |
| `*_phase.py` (all 7) | Each defines a `specialist_system_prompt` property with domain-specific instructions |

---

*Last updated: March 2026*
