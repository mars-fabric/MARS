# RFP Proposal Generator — Complete Flow Diagram

## Master Flow Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER (Browser)                                     │
│                                                                                 │
│  1. Open Task Catalog → Select "RFP Proposal Generator"                        │
│  2. Upload PDF / Paste RFP text → Pick model → Click "Analyze Requirements"    │
│  3. Review & edit each stage → Click "Next Stage"                              │
│  4. Download final proposal (MD / PDF)                                          │
└───────┬─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND  (React / Next.js)                              │
│                                                                                 │
│  RfpProposalTask.tsx ── 8-step wizard (Step 0 = Setup, Steps 1–7 = Stages)     │
│  useRfpTask.ts       ── state machine, REST calls, WebSocket, polling          │
│  RfpSetupPanel       ── file upload, RFP input, model config                   │
│  RfpReviewPanel      ── editor + refinement chat (Steps 1–6)                   │
│  RfpProposalPanel    ── final proposal preview + download (Step 7)             │
└───────┬──────────────────────────────┬──────────────────────────────────────────┘
        │  REST API (HTTP)             │  WebSocket (ws://)
        ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        BACKEND  (FastAPI / Python)                               │
│                                                                                 │
│  routers/rfp.py       ── 14 REST endpoints + execution engine                  │
│  main.py              ── WebSocket /ws/rfp/{task_id}/{stage_num}               │
│  services/             ── pdf_extractor.py, session_manager.py                  │
│  phases/rfp/           ── 7 Phase classes + base + token_utils + agent_teams    │
└───────┬──────────────────────────────┬──────────────────────────────────────────┘
        │                              │
        ▼                              ▼
┌────────────────────────┐  ┌─────────────────────────────────────────────────────┐
│   DATABASE  (SQLite)   │  │   LLM API  (OpenAI / Azure / Gemini / Claude)       │
│                        │  │                                                     │
│  Session               │  │   3 calls per stage (Primary → Specialist → Review) │
│  WorkflowRun           │  │   = 21 LLM calls for 7 stages                      │
│  TaskStage (×7)        │  │   + refinement chat calls (on-demand)               │
│  CostRecord            │  │                                                     │
└────────────────────────┘  └─────────────────────────────────────────────────────┘
```

---

## 1. Task Creation Flow

```
USER                          FRONTEND                         BACKEND                          DATABASE
 │                               │                               │                                │
 │  Upload PDF file              │                               │                                │
 ├──────────────────────────────►│                               │                                │
 │                               │  (no task yet? auto-create)   │                                │
 │                               │  POST /api/rfp/create         │                                │
 │                               │  { task: "", config: {} }     │                                │
 │                               ├──────────────────────────────►│                                │
 │                               │                               │  uuid4() → task_id             │
 │                               │                               │  uuid4() → session_id          │
 │                               │                               │                                │
 │                               │                               │  SessionManager.create_session()│
 │                               │                               ├───────────────────────────────►│
 │                               │                               │  INSERT Session                │
 │                               │                               │    id=session_id               │
 │                               │                               │    name="RFP: {text[:60]}"     │
 │                               │                               │    status="active"             │
 │                               │                               │    mode="rfp-proposal"         │
 │                               │                               │                                │
 │                               │                               │  INSERT WorkflowRun            │
 │                               │                               ├───────────────────────────────►│
 │                               │                               │    id=task_id                  │
 │                               │                               │    session_id=session_id       │
 │                               │                               │    mode="rfp-proposal"         │
 │                               │                               │    agent="phase_orchestrator"  │
 │                               │                               │    model=WorkflowConfig model  │
 │                               │                               │    status="executing"          │
 │                               │                               │    meta={work_dir, rfp_context,│
 │                               │                               │          config, session_id}   │
 │                               │                               │                                │
 │                               │                               │  mkdir work_dir/input_files/   │
 │                               │                               │                                │
 │                               │                               │  ×7 INSERT TaskStage           │
 │                               │                               ├───────────────────────────────►│
 │                               │                               │    stage_number=1..7           │
 │                               │                               │    stage_name=STAGE_DEFS[n]    │
 │                               │                               │    status="pending"            │
 │                               │                               │    parent_run_id=task_id       │
 │                               │                               │                                │
 │                               │  ◄── { task_id, work_dir,     │                                │
 │                               │       stages: [7 pending] }   │                                │
 │                               │◄──────────────────────────────┤                                │
 │                               │                               │                                │
 │                               │  POST /api/files/upload       │                                │
 │                               │  FormData: file + task_id     │                                │
 │                               ├──────────────────────────────►│                                │
 │                               │                               │  Save file to input_files/     │
 │                               │                               │  extract_pdf_content(fitz)     │
 │                               │                               │    → text blocks               │
 │                               │                               │    → markdown tables           │
 │                               │                               │    → image descriptions        │
 │                               │  ◄── { path, extracted_text } │                                │
 │                               │◄──────────────────────────────┤                                │
 │                               │                               │                                │
 │  See extracted text in        │                               │                                │
 │  textarea (auto-populated)    │                               │                                │
 │◄──────────────────────────────┤                               │                                │
 │                               │                               │                                │
 │  Edit RFP text + add context  │                               │                                │
 │  Click "Analyze Requirements" │                               │                                │
 ├──────────────────────────────►│                               │                                │
 │                               │  PATCH /{task_id}/description │                                │
 │                               │  { task, rfp_context }        │                                │
 │                               ├──────────────────────────────►│                                │
 │                               │                               │  UPDATE WorkflowRun            │
 │                               │                               │    task_description = task      │
 │                               │                               │    meta.rfp_context = context  │
 │                               │                               ├───────────────────────────────►│
 │                               │                               │                                │
 │                               │  Save rfp_input.md + context  │                                │
 │                               │                               │  write input_files/rfp_input.md│
 │                               │                               │  write input_files/rfp_context │
 │                               │                               │                                │
 │                               │  ─── TRIGGER STAGE 1 ──────► │                                │
```

---

## 2. Stage Execution Flow (Stages 1–7)

```
FRONTEND (useRfpTask)             BACKEND (routers/rfp.py)          PHASE ENGINE              DATABASE         LLM API
 │                                   │                                │                          │                │
 │  POST /{id}/stages/{N}/execute    │                                │                          │                │
 │  { config_overrides: {model} }    │                                │                          │                │
 ├──────────────────────────────────►│                                │                          │                │
 │                                   │                                │                          │                │
 │                                   │  UPDATE TaskStage              │                          │                │
 │                                   │    status → "running"          │                          │                │
 │                                   │    started_at → now()          │                          │                │
 │                                   ├─────────────────────────────────────────────────────────►│                │
 │                                   │                                │                          │                │
 │                                   │  asyncio.create_task(          │                          │                │
 │                                   │    _run_rfp_stage(...)         │                          │                │
 │                                   │  )                             │                          │                │
 │                                   │  ┌────────────────────────────►│                          │                │
 │  ◄── { status: "executing" }      │  │                             │                          │                │
 │◄──────────────────────────────────┤  │                             │                          │                │
 │                                   │  │                             │                          │                │
 │  Open WebSocket                   │  │  BACKGROUND TASK:           │                          │                │
 │  ws://host/ws/rfp/{id}/{N}       │  │                             │                          │                │
 ├──────────────────────────────────►│  │  1. build_shared_state()    │                          │                │
 │  ◄── { type: "status" }          │  │     SELECT TaskStage WHERE  │                          │                │
 │◄──────────────────────────────────┤  │     parent_run_id=task_id   │                          │                │
 │                                   │  │     AND stage_number < N    │                          │                │
 │  Start console poll (2s)          │  │     AND status="completed"  │                          │                │
 │  GET .../console?since=0          │  │     → merge output_data     │                          │                │
 ├──────────────────────────────────►│  │       ["shared"] dicts      │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  2. _build_rfp_context()    │                          │                │
 │                                   │  │     Scan uploaded files     │                          │                │
 │                                   │  │     Extract PDF content     │                          │                │
 │                                   │  │     Build context string    │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  3. Install console capture │                          │                │
 │                                   │  │     sys.stdout =            │                          │                │
 │                                   │  │       _ConsoleCapture(key)  │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  4. _load_phase_class(N)    │                          │                │
 │                                   │  │     importlib.import_module │                          │                │
 │                                   │  │     → PhaseClass            │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  5. PhaseClass(config)      │                          │                │
 │                                   │  │     → phase instance        │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  6. PhaseContext(           │                          │                │
 │                                   │  │       task, work_dir,       │                          │                │
 │                                   │  │       shared_state)         │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  7. await phase.execute(ctx)│                          │                │
 │                                   │  │     ─────────────────────►  │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │     ┌───────────────────────┴──────────────────────────┴────────────────┐
 │                                   │  │     │            PHASE EXECUTE PIPELINE (see §3 below)                  │
 │                                   │  │     └───────────────────────┬──────────────────────────┬────────────────┘
 │                                   │  │                             │                          │                │
 │  ◄── WS: console_output lines     │  │     ◄── PhaseResult        │                          │                │
 │◄──────────────────────────────────┤  │                             │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  8. Extract cost from result│                          │                │
 │                                   │  │     prompt_tokens,          │                          │                │
 │                                   │  │     completion_tokens       │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  9. INSERT CostRecord       │                          │                │
 │                                   │  │     run_id=task_id          │                          │                │
 │                                   │  │     model, tokens, cost_usd │                          │                │
 │                                   │  ├─────────────────────────────────────────────────────►  │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  10. Write output to file   │                          │                │
 │                                   │  │      input_files/{stage}.md │                          │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  11. UPDATE TaskStage       │                          │                │
 │                                   │  │      status → "completed"   │                          │                │
 │                                   │  │      output_data = {        │                          │                │
 │                                   │  │        shared: {key: text}, │                          │                │
 │                                   │  │        artifacts: {model},  │                          │                │
 │                                   │  │        cost: {tokens}       │                          │                │
 │                                   │  │      }                      │                          │                │
 │                                   │  ├─────────────────────────────────────────────────────►  │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  12. If ALL stages completed│                          │                │
 │                                   │  │      → UPDATE WorkflowRun   │                          │                │
 │                                   │  │        status="completed"   │                          │                │
 │                                   │  │        completed_at=now()   │                          │                │
 │                                   │  ├─────────────────────────────────────────────────────►  │                │
 │                                   │  │                             │                          │                │
 │                                   │  │  13. _generate_cost_summary()                          │                │
 │                                   │  │      Read each stage's      │                          │                │
 │                                   │  │        output_data["cost"]   │                          │                │
 │                                   │  │      Build per-stage table   │                          │                │
 │                                   │  │      Write cost_summary.md   │                          │                │
 │                                   │  │        to input_files/       │                          │                │
 │                                   │  │                             │                          │                │
 │  ◄── WS: stage_completed          │  │                             │                          │                │
 │◄──────────────────────────────────┤  │                             │                          │                │
 │                                   │  └──── cleanup: restore stdout │                          │                │
 │                                   │                                │                          │                │
 │  GET /{id}/stages/{N}/content     │                                │                          │                │
 │  (fetch completed output)         │                                │                          │                │
 ├──────────────────────────────────►│                                │                          │                │
 │                                   │  SELECT TaskStage              │                          │                │
 │                                   │  → output_data["shared"][key]  │                          │                │
 │                                   ├─────────────────────────────────────────────────────────►│                │
 │  ◄── { content, shared_state }    │                                │                          │                │
 │◄──────────────────────────────────┤                                │                          │                │
 │                                   │                                │                          │                │
 │  Display in editor panel          │                                │                          │                │
```

---

## 3. Phase Execute Pipeline (Inside `phase.execute(ctx)`)

```
RfpPhaseBase.execute(context)
 │
 │  ┌─────────────────────────────────────────────────────────────┐
 │  │  A. BUILD PROMPTS                                           │
 │  │                                                             │
 │  │  system_prompt ← self.system_prompt (persona for stage)     │
 │  │  user_prompt   ← self.build_user_prompt(context)            │
 │  │                  └── Reads from context.shared_state:       │
 │  │                      Stage 1: rfp_content + rfp_context     │
 │  │                      Stage 2: + requirements_analysis       │
 │  │                      Stage 3: + tools_technology             │
 │  │                      Stage 4: + cloud_infrastructure         │
 │  │                      Stage 5: + implementation_plan          │
 │  │                      Stage 6: + architecture_design          │
 │  │                      Stage 7: ALL 6 prior outputs            │
 │  │                                                             │
 │  │  currency_rule ← get_currency_rule(context)                 │
 │  │                  └── 3-pass detection:                       │
 │  │                      Pass 1: Scan requirements for          │
 │  │                              "Primary Currency: XXX"         │
 │  │                      Pass 2: Scan original RFP for          │
 │  │                              symbols / ISO codes             │
 │  │                      Pass 3: Default USD ($)                │
 │  │                                                             │
 │  │  user_prompt += currency_rule                               │
 │  └─────────────────────────────────────────────────────────────┘
 │
 │  ┌─────────────────────────────────────────────────────────────┐
 │  │  B. TOKEN CAPACITY CHECK                                    │
 │  │                                                             │
 │  │  max_ctx, max_out = get_model_limits(model)                 │
 │  │  prompt_tokens = count_tokens(system + user, model)         │
 │  │  usable_ctx = int(max_ctx × 0.75) - max_completion_tokens   │
 │  │                                                             │
 │  │  IF prompt_tokens ≤ usable_ctx:                             │
 │  │     → SINGLE CALL path                                      │
 │  │  ELSE:                                                      │
 │  │     → CHUNKED path (split at "---" boundaries)              │
 │  └─────────────────────────────────────────────────────────────┘
 │
 ▼
╔═════════════════════════════════════════════════════════════════╗
║  PASS 1: PRIMARY AGENT (Generation)                            ║
║                                                                ║
║  LLM Call #1                                                   ║
║  ┌───────────────────────────────────┐                         ║
║  │  system: Expert persona           │                         ║
║  │  user:   RFP + prior stages       │   ────►  LLM API       ║
║  │  model:  config.model             │                         ║
║  │  temp:   0.7                      │   ◄────  draft content  ║
║  │  max_completion_tokens: dynamic   │         (markdown)      ║
║  └───────────────────────────────────┘                         ║
║                                                                ║
║  (If chunked: multiple sub-calls → concatenate results)        ║
╚════════════════════════════════╦════════════════════════════════╝
                                 │  draft content
                                 ▼
╔═════════════════════════════════════════════════════════════════╗
║  PASS 2: SPECIALIST AGENT (if multi_agent=True)                ║
║                                                                ║
║  LLM Call #2                                                   ║
║  ┌───────────────────────────────────┐                         ║
║  │  system: Specialist persona       │                         ║
║  │          (from agent_teams.py)    │                         ║
║  │  user:   draft + validation       │   ────►  LLM API       ║
║  │          instructions +           │                         ║
║  │          currency_rule            │   ◄────  improved       ║
║  │  model:  specialist_model or same │         content         ║
║  └───────────────────────────────────┘                         ║
║                                                                ║
║  Specialist roles per stage:                                   ║
║    Stage 1: Domain Validation Expert                           ║
║    Stage 2: Security & Compliance Auditor                      ║
║    Stage 3: Cloud Cost Optimisation Specialist                 ║
║    Stage 4: Delivery Assurance Analyst                         ║
║    Stage 5: Scalability & Implementation Engineer              ║
║    Stage 6: Risk & Governance Specialist                       ║
║    Stage 7: Senior Proposal Editor                             ║
╚════════════════════════════════╦════════════════════════════════╝
                                 │  improved content
                                 ▼
╔═════════════════════════════════════════════════════════════════╗
║  PASS 3: REVIEWER AGENT (×n_reviews, default 1)               ║
║                                                                ║
║  LLM Call #3                                                   ║
║  ┌───────────────────────────────────┐                         ║
║  │  system: 13-point quality         │                         ║
║  │          checklist reviewer        │                         ║
║  │  user:   "Draft document:\n\n" +  │   ────►  LLM API       ║
║  │          improved_content +       │                         ║
║  │          currency_rule            │   ◄────  polished       ║
║  │  model:  review_model or same     │         content         ║
║  └───────────────────────────────────┘                         ║
║                                                                ║
║  13-Point Review Checklist:                                    ║
║   1. Fix factual errors                                        ║
║   2. Improve structure & flow                                  ║
║   3. Verify cost figures present & consistent                  ║
║   4. Ensure comparison tables for tools                        ║
║   5. Verify security comparisons                               ║
║   6. Verify cloud provider comparisons                         ║
║   7. Add professional tables                                   ║
║   8. Replace ALL placeholders                                  ║
║   9. Enforce single consistent currency                        ║
║  10. Monthly + Annual cost columns                             ║
║  11. Annual = Monthly × 12                                     ║
║  12. Real content in appendices                                ║
║  13. Enterprise-quality prose                                  ║
╚════════════════════════════════╦════════════════════════════════╝
                                 │  final content
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  C. SAVE & RETURN                                               │
│                                                                 │
│  Write to: {work_dir}/input_files/{output_filename}             │
│                                                                 │
│  Return PhaseResult:                                            │
│    output_data = {                                              │
│      "shared": { shared_output_key: final_content },            │
│      "artifacts": { "model": model },                           │
│      "cost": { "prompt_tokens": X, "completion_tokens": Y }    │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Stage 7 Special: Divide-and-Accumulate Strategy

```
RfpProposalPhase.execute(context)
 │
 │  Collect all 6 source keys from shared_state:
 │    requirements_analysis, tools_technology, cloud_infrastructure,
 │    implementation_plan, architecture_design, execution_strategy
 │
 │  Count total prompt tokens (system + all 6 sources)
 │
 ├── PATH A: All sources fit context window?
 │   │
 │   │  YES → Single _single_generate() call
 │   │         (system prompt + all 6 sources + proposal template)
 │   │             │
 │   │             ├── Output non-empty? → Continue to specialist + review
 │   │             │
 │   │             └── Output empty/short? → FALL THROUGH to PATH B
 │   │
 │   └── NO ──────────────────────────────────────────────┐
 │                                                         │
 ▼                                                         ▼
 PATH B: Divide-and-Accumulate
 │
 │  1. group_sources_by_budget(6 sources, model, safety=0.75)
 │     → Divide into N groups that each fit context
 │     Example: Group 1 = [requirements, tools, cloud]
 │              Group 2 = [implementation, architecture, execution]
 │
 │  2. For each group:
 │     ├── _build_partial_prompt(group_keys)
 │     │   → Only relevant proposal sections for these sources
 │     │
 │     ├── _single_generate(partial_prompt)
 │     │   → Partial proposal markdown
 │     │
 │     └── Collect partial result
 │
 │  3. Accumulation pass:
 │     ├── Merge all partial proposals
 │     ├── Remove duplicate sections
 │     ├── Ensure cover page, exec summary, appendices present
 │     └── → Complete proposal.md
 │
 ▼
 Continue to specialist + review (same as stages 1–6)
```

---

## 5. Shared State Accumulation Across Stages

```
Stage 1 executes
  │  Output: { "shared": { "requirements_analysis": "..." } }
  │  Saved to: requirements.md
  │  DB: TaskStage[1].output_data.shared.requirements_analysis
  ▼
Stage 2 reads shared_state = { requirements_analysis }
  │  Output: { "shared": { "requirements_analysis": "...", "tools_technology": "..." } }
  │  Saved to: tools.md
  │  DB: TaskStage[2].output_data.shared.tools_technology
  ▼
Stage 3 reads shared_state = { requirements_analysis, tools_technology }
  │  Output: + cloud_infrastructure
  │  Saved to: cloud.md
  ▼
Stage 4 reads shared_state = { requirements_analysis, tools_technology, cloud_infrastructure }
  │  Output: + implementation_plan
  │  Saved to: implementation.md
  ▼
Stage 5 reads shared_state = { ..., implementation_plan }
  │  Output: + architecture_design
  │  Saved to: architecture.md
  ▼
Stage 6 reads shared_state = { ..., architecture_design }
  │  Output: + execution_strategy
  │  Saved to: execution.md
  ▼
Stage 7 reads ALL 6 shared_state keys
  │  Output: proposal_compilation (complete proposal)
  │  Saved to: proposal.md
  ▼
ALL stages completed → WorkflowRun.status = "completed"


build_shared_state(task_id, up_to_stage=N):
  ┌──────────────────────────────────────────────┐
  │  SELECT TaskStage                             │
  │  WHERE parent_run_id = task_id                │
  │    AND stage_number < N                       │
  │    AND status = "completed"                   │
  │  ORDER BY stage_number                        │
  │                                               │
  │  shared = {}                                  │
  │  for stage in results:                        │
  │      shared.update(stage.output_data["shared"])│
  │  return shared                                │
  └──────────────────────────────────────────────┘
```

---

## 6. Database Entity Relationship

```
┌────────────────────┐       ┌─────────────────────────┐
│     Session         │       │      WorkflowRun         │
├────────────────────┤       ├─────────────────────────┤
│ id (PK)            │◄──────│ session_id (FK)          │
│ name               │  1:N  │ id (PK) = task_id        │
│ status             │       │ mode = "rfp-proposal"    │
│ meta               │       │ agent = "phase_orch..."  │
│ created_at         │       │ model                    │
│ last_active_at     │       │ status                   │
└────────────────────┘       │ task_description         │
                              │ started_at               │
                              │ completed_at             │
                              │ meta (JSON)              │
                              └──────────┬──────────────┘
                                         │ 1:N
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
     ┌──────────────────────┐  ┌──────────────┐   (repeated ×7)
     │    CostRecord         │  │  TaskStage    │
     ├──────────────────────┤  ├──────────────┤
     │ id (PK)              │  │ id (PK)       │
     │ run_id (FK)──────────┤  │ parent_run_id │──► WorkflowRun.id
     │ model                │  │ stage_number  │   (1..7)
     │ prompt_tokens        │  │ stage_name    │
     │ completion_tokens    │  │ status        │   pending → running
     │ cost_usd             │  │ input_data    │   → completed / failed
     │ timestamp            │  │ output_data   │   (JSON with shared,
     └──────────────────────┘  │ output_files  │    artifacts, cost)
                                │ error_message │
                                │ started_at    │
                                │ completed_at  │
                                └───────────────┘


DB Operations Timeline per Task:
  CREATE  → 1 Session + 1 WorkflowRun + 7 TaskStages (all "pending")
  EXECUTE → per stage: UPDATE TaskStage → "running"
                        → "completed" + output_data
                        INSERT CostRecord
  FINAL   → UPDATE WorkflowRun → "completed" (after stage 7)
  EDIT    → UPDATE TaskStage.output_data (user edits in review panel)
  RESET   → UPDATE TaskStage(s) → "pending" (stages N..7)
  STOP    → UPDATE TaskStage → "failed", WorkflowRun → "failed"
  DELETE  → DELETE WorkflowRun (CASCADE → TaskStages, CostRecords)
```

---

## 7. User Edit & Refinement Flow

```
USER                          FRONTEND                       BACKEND                        DATABASE
 │                               │                              │                              │
 │  Edit content in editor       │                              │                              │
 ├──────────────────────────────►│                              │                              │
 │                               │  (1s debounce auto-save)     │                              │
 │                               │  PUT /{id}/stages/{N}/content│                              │
 │                               │  { content, field }          │                              │
 │                               ├─────────────────────────────►│                              │
 │                               │                              │  UPDATE TaskStage            │
 │                               │                              │    output_data["shared"]     │
 │                               │                              │      [field] = content       │
 │                               │                              ├─────────────────────────────►│
 │                               │                              │                              │
 │                               │                              │  Write to {stage}.md file    │
 │                               │                              │                              │
 │  ────────── OR ──────────     │                              │                              │
 │                               │                              │                              │
 │  Type refinement message      │                              │                              │
 │  "Add more detail to the      │                              │                              │
 │   security section"           │                              │                              │
 ├──────────────────────────────►│                              │                              │
 │                               │  POST /{id}/stages/{N}/refine│                              │
 │                               │  { message, content }        │                              │
 │                               ├─────────────────────────────►│                              │
 │                               │                              │                              │
 │                               │                              │  Token capacity check        │
 │                               │                              │  (trim content if overflow)  │
 │                               │                              │                              │
 │                               │                              │  LLM call:                  │
 │                               │                              │    system: "technical        │
 │                               │                              │      proposal consultant"    │
 │                               │                              │    user: content +           │
 │                               │                              │      instruction             │────► LLM API
 │                               │                              │                              │◄──── refined
 │                               │                              │                              │
 │                               │  ◄── { refined_content }     │                              │
 │                               │◄─────────────────────────────┤                              │
 │                               │                              │                              │
 │  See refined content          │  Auto-save refined content   │                              │
 │  in editor                    │  PUT /{id}/stages/{N}/content│                              │
 │◄──────────────────────────────┤  (same as manual edit)       │                              │
 │                               ├─────────────────────────────►│                              │
```

---

## 8. Task Resumption Flow

```
USER                          FRONTEND                       BACKEND
 │                               │                              │
 │  Open RFP task page           │                              │
 │  (mount RfpProposalTask)      │                              │
 ├──────────────────────────────►│                              │
 │                               │  GET /api/rfp/recent         │
 │                               ├─────────────────────────────►│
 │                               │                              │  SELECT WorkflowRun
 │                               │                              │  WHERE mode="rfp-proposal"
 │                               │                              │    AND status="executing"
 │                               │  ◄── [incomplete tasks]      │
 │                               │◄─────────────────────────────┤
 │                               │                              │
 │  See "In Progress" cards      │                              │
 │  above setup panel            │                              │
 │◄──────────────────────────────┤                              │
 │                               │                              │
 │  Click resume arrow on card   │                              │
 ├──────────────────────────────►│                              │
 │                               │  resumeTask(taskId)          │
 │                               │  GET /api/rfp/{taskId}       │
 │                               ├─────────────────────────────►│
 │                               │  ◄── full task state         │  SELECT WorkflowRun + TaskStages
 │                               │◄─────────────────────────────┤
 │                               │                              │
 │                               │  Determine resume step:      │
 │                               │  ┌──────────────────────────┐│
 │                               │  │ for stage in stages:     ││
 │                               │  │   if "running":          ││
 │                               │  │     → reconnect WS       ││
 │                               │  │     → resume poll        ││
 │                               │  │     → step = stage_num   ││
 │                               │  │   if "completed":        ││
 │                               │  │     → step = num + 1     ││
 │                               │  │   if "failed"/"pending": ││
 │                               │  │     → step = num (retry) ││
 │                               │  │     → break              ││
 │                               │  └──────────────────────────┘│
 │                               │                              │
 │  Jump to correct wizard step  │                              │
 │◄──────────────────────────────┤                              │
```

---

## 9. Stop, Reset & Delete Flows

### Stop (Cancel Running Stage)

```
USER → POST /api/rfp/{task_id}/stop
         │
         ├── Cancel asyncio background task (_running_tasks[key].cancel())
         │
         ├── UPDATE TaskStage (running ones)
         │     status → "failed"
         │     error_message → "Stopped by user"
         │
         └── UPDATE WorkflowRun
               status → "failed"
```

### Reset from Stage N

```
USER → POST /api/rfp/{task_id}/reset-from/{N}
         │
         ├── For each TaskStage WHERE stage_number ≥ N:
         │     UPDATE status → "pending"
         │     CLEAR started_at, completed_at, error_message
         │     DELETE generated file from disk ({stage}.md)
         │
         └── UPDATE WorkflowRun
               status → "executing" (re-open for execution)
```

### Delete Task

```
USER → DELETE /api/rfp/{task_id}
         │
         ├── Cancel any running background tasks
         │
         ├── DELETE WorkflowRun (CASCADE → TaskStages, CostRecords)
         │
         └── shutil.rmtree(work_dir)  (delete all files)
```

---

## 10. WebSocket Real-Time Communication

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    WebSocket Lifecycle                                        │
│                                                                              │
│  FRONTEND                              BACKEND (/ws/rfp/{id}/{stage})        │
│                                                                              │
│  1. connectWs(id, stageNum)            Accept connection                    │
│     ws://host/ws/rfp/{id}/{N}  ──────► │                                    │
│                                        │                                    │
│  2. ◄── {"event_type": "status",    ◄── Send initial status                  │
│          "message": "Connected"}       │                                    │
│                                        │                                    │
│  3. Loop every 1 second:              │  Check _console_buffers[key]        │
│     ◄── {"event_type":              ◄── │  for new lines since last send    │
│          "console_output",             │                                    │
│          "text": "...line..."}         │                                    │
│                                        │                                    │
│     ◄── {"event_type":              ◄── │  (Token budget info, LLM calls,   │
│          "console_output",             │   progress messages)              │
│          "text": "[Stage N] ..."}      │                                    │
│                                        │                                    │
│  4. ◄── {"event_type":              ◄── │  Poll DB: stage.status changed    │
│          "stage_completed",            │  to "completed"                   │
│          "stage_num": N}               │                                    │
│     OR                                 │                                    │
│     ◄── {"event_type":              ◄── │  to "failed"                     │
│          "stage_failed",               │                                    │
│          "error": "reason"}            │                                    │
│                                        │                                    │
│  5. Close connection                   │  _clear_console_buffer(key)        │
│     ──────────────────────────────────►│  Break loop                       │
│                                        │                                    │
│  PARALLEL: Console REST polling        │                                    │
│  GET .../console?since={idx}  ────────►│  Read _console_buffers[key][idx:]  │
│  ◄── {"lines": [...], "next": N}  ◄───│  (backup if WS drops)             │
└──────────────────────────────────────────────────────────────────────────────┘

Console Buffer (thread-safe):
  _console_buffers: Dict[str, List[str]]
    Key format: "{task_id}:{stage_num}"
    _ConsoleCapture writes to both buffer + original stdout
    Protected by _console_lock (threading.Lock)
```

---

## 11. File Upload & PDF Extraction Flow

```
USER                       FRONTEND                    BACKEND                     FILESYSTEM
 │                            │                           │                            │
 │  Select PDF file           │                           │                            │
 ├───────────────────────────►│                           │                            │
 │                            │  (auto-create task        │                            │
 │                            │   if needed)              │                            │
 │                            │                           │                            │
 │                            │  POST /api/files/upload   │                            │
 │                            │  FormData:                │                            │
 │                            │    file: <binary>         │                            │
 │                            │    task_id: {id}          │                            │
 │                            │    subfolder: input_files │                            │
 │                            ├──────────────────────────►│                            │
 │                            │                           │  Save to:                  │
 │                            │                           │  {work_dir}/input_files/   │
 │                            │                           │    {original_filename}     │
 │                            │                           ├───────────────────────────►│
 │                            │                           │                            │
 │                            │                           │  Is PDF?                   │
 │                            │                           │  → extract_pdf_content()   │
 │                            │                           │                            │
 │                            │                           │  ┌────────────────────────┐│
 │                            │                           │  │  PyMuPDF (fitz)        ││
 │                            │                           │  │                        ││
 │                            │                           │  │  For each page:        ││
 │                            │                           │  │    find_tables()       ││
 │                            │                           │  │    → markdown tables   ││
 │                            │                           │  │                        ││
 │                            │                           │  │    extract text blocks ││
 │                            │                           │  │    (skip table regions)││
 │                            │                           │  │                        ││
 │                            │                           │  │    extract image info  ││
 │                            │                           │  │    → dimensions/format ││
 │                            │                           │  │                        ││
 │                            │                           │  │  Cap at 512KB          ││
 │                            │                           │  │  Escape { → {{ } → }}  ││
 │                            │                           │  └────────────────────────┘│
 │                            │                           │                            │
 │                            │  ◄── {path, extracted_text}                            │
 │                            │◄──────────────────────────┤                            │
 │                            │                           │                            │
 │  Textarea auto-fills       │                           │                            │
 │  with extracted text       │                           │                            │
 │◄───────────────────────────┤                           │                            │
 │                            │                           │                            │
 │                            │                           │                            │
 │  ═══ LATER: Stage Execute ═══                          │                            │
 │                            │                           │                            │
 │                            │                           │  _build_rfp_context()      │
 │                            │                           │  Scan input_files/ for     │
 │                            │                           │  uploaded files (not .md)  │
 │                            │                           │  Extract each PDF again    │
 │                            │                           │  Build context string      │
 │                            │                           │  → inject into prompt      │
```

---

## 12. Cost Tracking Flow

```
PHASE ENGINE                          BACKEND                          DATABASE
 │                                       │                                │
 │  LLM call returns:                    │                                │
 │    usage.prompt_tokens = 5000         │                                │
 │    usage.completion_tokens = 3000     │                                │
 │                                       │                                │
 │  PhaseResult.output_data["cost"] = {  │                                │
 │    "prompt_tokens": 5000,             │                                │
 │    "completion_tokens": 3000          │                                │
 │  }                                    │                                │
 ├──────────────────────────────────────►│                                │
 │                                       │  cost_usd = (5000 × 0.002     │
 │                                       │           + 3000 × 0.008)     │
 │                                       │           / 1000              │
 │                                       │         = $0.034              │
 │                                       │                                │
 │                                       │  INSERT CostRecord            │
 │                                       │    run_id = task_id            │
 │                                       │    model = "gpt-4o"           │
 │                                       │    prompt_tokens = 5000       │
 │                                       │    completion_tokens = 3000   │
 │                                       │    cost_usd = 0.034           │
 │                                       ├───────────────────────────────►│
 │                                       │                                │
 │                                       │  Store cost in stage's         │
 │                                       │  output_data["cost"] = {       │
 │                                       │    prompt_tokens, completion,  │
 │                                       │    cost_usd                    │
 │                                       │  }                             │
 │                                       ├───────────────────────────────►│
 │                                       │                                │
 │                                       │                                │
 ═══ ALL 7 STAGES COMPLETED ═══          │                                │
                                         │                                │
                                         │  _generate_cost_summary()      │
                                         │    Read each TaskStage's       │
                                         │    output_data["cost"]          │
                                         │                                │
                                         │  Write cost_summary.md:        │
                                         │  ┌────────────────────────────┐│
                                         │  │ # RFP Proposal — Cost      ││
                                         │  │ ## Per-Stage Breakdown     ││
                                         │  │ | # | Stage | Model | ... ││
                                         │  │ |---|-------|-------|-----││
                                         │  │ | 1 | Requirements | ... ││
                                         │  │ | 2 | Tools & Tech | ... ││
                                         │  │ | … | …            | … | ││
                                         │  │ |   | **TOTAL**    | ... ││
                                         │  │ ## Summary                ││
                                         │  │ - Total Tokens: 70,000    ││
                                         │  │ - Total Cost: $0.3080     ││
                                         │  └────────────────────────────┘│
                                         │  → input_files/cost_summary.md │
                                         │                                │
                                         │                                │
 ═══ FRONTEND QUERIES COST ═══           │                                │
                                         │                                │
 GET /api/rfp/{task_id}                  │                                │
 ────────────────────────────────────────►│                                │
                                         │  get_task_total_cost(task_id)  │
                                         │  SELECT SUM(cost_usd),        │
                                         │    SUM(total_tokens)          │
                                         │  FROM cost_records             │
                                         │  WHERE run_id=task_id          │
                                         │◄───────────────────────────────│
                                         │                                │
 ◄── { total_cost_usd: 0.238 }          │                                │
 ◄───────────────────────────────────────┤                                │

 GET /api/rfp/{id}/download/cost_summary.md
 ────────────────────────────────────────►│
                                         │  FileResponse(cost_summary.md) │
 ◄── cost_summary.md file                │                                │
 ◄───────────────────────────────────────┤                                │
```

---

## 13. Complete End-to-End User Journey

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                             │
│   ① SETUP (Step 0)                                                                         │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • See "In Progress" cards (if any, scrollable >5)   │                                   │
│   │  • Upload RFP PDF → auto-extract text               │                                   │
│   │  • Paste/edit RFP text in textarea                  │                                   │
│   │  • Add optional context                             │                                   │
│   │  • Select model (gear icon → model dropdown)        │                                   │
│   │  • Click "Analyze Requirements" ────────────────────┼──► Creates task + 7 stages in DB  │
│   └─────────────────────────────────────────────────────┘    Triggers Stage 1 execution     │
│       │                                                                                     │
│       ▼                                                                                     │
│   ② REQUIREMENTS ANALYSIS (Step 1)                                                         │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • Console shows live LLM progress                  │                                   │
│   │  • 3 LLM calls: Primary → Specialist → Reviewer     │                                   │
│   │  • Output: requirements.md                          │                                   │
│   │  • Resizable split: editor + refinement chat        │                                   │
│   │    (both panes shrinkable to 200px min)             │                                   │
│   │  • User reviews, edits, or refines via chat         │                                   │
│   │  • Click "Next" → triggers Stage 2 ────────────────┼──► Saves edits + executes next    │
│   └─────────────────────────────────────────────────────┘                                   │
│       │                                                                                     │
│       ▼                                                                                     │
│   ③ TOOLS & TECHNOLOGY (Step 2)  ─── same pattern ───                                      │
│   ④ CLOUD & INFRASTRUCTURE (Step 3)                                                        │
│   ⑤ IMPLEMENTATION PLAN (Step 4)                                                           │
│   ⑥ ARCHITECTURE DESIGN (Step 5)                                                           │
│   ⑦ EXECUTION STRATEGY (Step 6)                                                            │
│       │                                                                                     │
│       │  Each step: execute stage → review/edit → advance                                   │
│       │  Each stage reads ALL prior stages' output from DB                                  │
│       │  Human edits flow forward to subsequent stages                                      │
│       │                                                                                     │
│       ▼                                                                                     │
│   ⑧ PROPOSAL COMPILATION (Step 7)                                                          │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • Reads all 6 prior stage outputs                  │                                   │
│   │  • Token check → single-shot or divide-accumulate   │                                   │
│   │  • 3 LLM calls (or more if divided)                 │                                   │
│   │  • Output: proposal.md (complete technical proposal)│                                   │
│   │  • Auto-generate cost_summary.md (per-stage + total)│                                   │
│   │  • Success banner with total cost                   │                                   │
│   │  • Download: all 7 artifacts + cost_summary.md      │                                   │
│   │  • Optional: Download as PDF                        │                                   │
│   └─────────────────────────────────────────────────────┘                                   │
│       │                                                                                     │
│       ▼                                                                                     │
│   ✓ COMPLETE                                                                                │
│     WorkflowRun.status → "completed"                                                        │
│     cost_summary.md written to input_files/                                                 │
│     Task removed from "In Progress" list                                                    │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Session & Database Lifecycle Summary

```
TIME ──────────────────────────────────────────────────────────────────────────────────►

TASK CREATION:
  ┌──────────┐   ┌──────────────┐   ┌────────────┐   ┌────────────┐
  │  Session  │   │ WorkflowRun  │   │ TaskStage  │   │ TaskStage  │  ... ×7
  │  INSERT   │──►│  INSERT      │──►│  INSERT    │──►│  INSERT    │
  │  active   │   │  executing   │   │  pending   │   │  pending   │
  └──────────┘   │  rfp-proposal │   │  stage 1   │   │  stage 2   │
                  └──────────────┘   └────────────┘   └────────────┘

STAGE 1 EXECUTE:
  TaskStage[1] → "running" ───► Phase.execute() ───► TaskStage[1] → "completed"
                                    │                    + output_data.shared
                                    └── CostRecord INSERT

STAGE 2 EXECUTE:
  build_shared_state(task, up_to=2) → reads TaskStage[1].output_data
  TaskStage[2] → "running" ───► Phase.execute() ───► TaskStage[2] → "completed"
                                    └── CostRecord INSERT

  ... repeat for stages 3–6 ...

STAGE 7 EXECUTE:
  build_shared_state(task, up_to=7) → reads ALL TaskStage[1-6].output_data
  TaskStage[7] → "running" ───► Phase.execute() ───► TaskStage[7] → "completed"
                                    └── CostRecord INSERT

  ALL 7 completed? → WorkflowRun → "completed", completed_at = now()
                   → _generate_cost_summary() → cost_summary.md
                     (per-stage table + totals from output_data["cost"])


USER EDITS (any time after stage completes):
  PUT /stages/{N}/content → UPDATE TaskStage[N].output_data["shared"][key]
                          → Write to {stage}.md file on disk


REFINEMENT CHAT (any time after stage completes):
  POST /stages/{N}/refine → LLM call → refined content
                           → auto-save via PUT


RESET FROM STAGE N:
  TaskStage[N..7] → "pending", clear output_data, delete .md files
  WorkflowRun → "executing"


STOP:
  Cancel asyncio tasks
  Running TaskStages → "failed" (error: "Stopped by user")
  WorkflowRun → "failed"


DELETE:
  WorkflowRun DELETE (CASCADE → all TaskStages + CostRecords)
  shutil.rmtree(work_dir)
```

---

## 15. API Endpoint Quick Reference

| # | Method | Path | Body | Response | DB Effect |
|---|--------|------|------|----------|-----------|
| 1 | POST | `/api/rfp/create` | `{task, rfp_context?, config?}` | `{task_id, work_dir, stages[]}` | INSERT Session + WorkflowRun + 7 TaskStages |
| 2 | GET | `/api/rfp/recent` | — | `[{task_id, task, status, stages, progress}]` | SELECT WorkflowRun WHERE status="executing" |
| 3 | GET | `/api/rfp/{id}` | — | `{task_id, stages, progress, cost}` | SELECT WorkflowRun + TaskStages + SUM(CostRecord) |
| 4 | POST | `/api/rfp/{id}/stages/{N}/execute` | `{config_overrides?}` | `{status: "executing"}` | UPDATE TaskStage → "running", spawns async task |
| 5 | GET | `/api/rfp/{id}/stages/{N}/content` | — | `{content, shared_state}` | SELECT TaskStage.output_data |
| 6 | PUT | `/api/rfp/{id}/stages/{N}/content` | `{content, field}` | `{status: "saved"}` | UPDATE TaskStage.output_data["shared"] |
| 7 | POST | `/api/rfp/{id}/stages/{N}/refine` | `{message, content}` | `{refined_content}` | LLM call only (no DB write) |
| 8 | GET | `/api/rfp/{id}/stages/{N}/console` | `?since=idx` | `{lines[], next_index}` | READ _console_buffers (in-memory) |
| 9 | POST | `/api/rfp/{id}/reset-from/{N}` | — | `{reset_count}` | UPDATE TaskStages[N..7] → "pending" |
| 10 | POST | `/api/rfp/{id}/stop` | — | `{status: "stopped"}` | UPDATE TaskStages → "failed", WorkflowRun → "failed" |
| 11 | GET | `/api/rfp/{id}/download/{file}` | — | FileResponse | READ file from disk |
| 12 | GET | `/api/rfp/{id}/download-pdf` | `?inline=bool` | FileResponse (PDF) | READ + convert proposal.md → PDF |
| 13 | DELETE | `/api/rfp/{id}` | — | `{status: "deleted"}` | DELETE WorkflowRun (CASCADE) + rmtree |
| 14 | PATCH | `/api/rfp/{id}/description` | `{task, rfp_context}` | `{status: "updated"}` | UPDATE WorkflowRun.task_description + meta |
| 15 | — | `ws://host/ws/rfp/{id}/{N}` | — | Events stream | READ TaskStage status + console buffer |
