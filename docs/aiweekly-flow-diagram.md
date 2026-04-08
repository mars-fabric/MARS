# AI Weekly Report Generator — Complete Flow Diagram

## Master Flow Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER (Browser)                                     │
│                                                                                 │
│  1. Open Task Catalog → Select "AI Weekly Report"                              │
│  2. Pick date range, topics, sources, style → Click "Collect Data"             │
│  3. Review & edit each stage → Click "Next Stage"                              │
│  4. Download final report (MD / PDF) + cost summary                            │
└───────┬─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND  (React / Next.js)                              │
│                                                                                 │
│  AIWeeklyReportTask.tsx ── 5-step wizard (Step 0 = Setup, Steps 1–4 = Stages)  │
│  useAIWeeklyTask.ts    ── state management, REST calls, polling                │
│  AIWeeklySetupPanel    ── date range, topics, sources, style, model config     │
│  AIWeeklyReviewPanel   ── editor + refinement chat (Steps 1–3)                 │
│  AIWeeklyReportPanel   ── final report preview + download (Step 4)             │
└───────┬─────────────────────────────────────────────────────────────────────────┘
        │ REST API (HTTP)
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        BACKEND  (FastAPI / Python)                               │
│                                                                                 │
│  routers/aiweekly.py   ── 13 REST endpoints + execution engine                 │
│    _run_aiweekly_stage():                                                       │
│      1. _load_phase_class(stage_num) ── importlib dynamic load                 │
│      2. PhaseClass(config=...)       ── instantiate phase                      │
│      3. PhaseContext(task, work_dir, shared_state)                              │
│      4. await phase.execute(ctx)     ── tool calls / LLM pipeline              │
│      5. Extract output, track cost (CostRecord), update DB                     │
│      6. On all-complete → _generate_cost_summary() → cost_summary.md           │
│                                                                                 │
│  _ConsoleCapture ── thread-safe stdout → REST console buffer                   │
└───────┬──────────────────────────────┬──────────────────────────────────────────┘
        │                              │
        ▼                              ▼
┌────────────────────────┐  ┌─────────────────────────────────────────────────────┐
│   DATABASE  (SQLite)   │  │   EXTERNAL APIs / LLM                               │
│                        │  │                                                     │
│  Session               │  │   Stage 1: RSS feeds, NewsAPI, GNews, web search    │
│  WorkflowRun           │  │            (no LLM — direct Python tool calls)      │
│  TaskStage (×4)        │  │                                                     │
│  CostRecord            │  │   Stages 2–3: 3 LLM calls per stage                │
│                        │  │     (Primary → Specialist → Reviewer)               │
│                        │  │   Stage 4: 2 LLM calls (Primary → Reviewer)        │
│                        │  │     = 8 LLM calls total + refinement (on-demand)    │
└────────────────────────┘  └─────────────────────────────────────────────────────┘
```

---

## 1. Task Creation Flow

```
USER                          FRONTEND                         BACKEND                          DATABASE
 │                               │                               │                                │
 │  Configure date range,        │                               │                                │
 │  topics, sources, style       │                               │                                │
 │  Click "Collect Data"         │                               │                                │
 ├──────────────────────────────►│                               │                                │
 │                               │  POST /api/aiweekly/create    │                                │
 │                               │  { date_from, date_to,        │                                │
 │                               │    topics, sources, style }   │                                │
 │                               ├──────────────────────────────►│                                │
 │                               │                               │  uuid4() → task_id             │
 │                               │                               │                                │
 │                               │                               │  SessionManager.create_session()│
 │                               │                               ├───────────────────────────────►│
 │                               │                               │  INSERT Session                │
 │                               │                               │    mode="aiweekly"             │
 │                               │                               │                                │
 │                               │                               │  INSERT WorkflowRun            │
 │                               │                               ├───────────────────────────────►│
 │                               │                               │    id=task_id                  │
 │                               │                               │    mode="aiweekly"             │
 │                               │                               │    agent="phase_orchestrator"  │
 │                               │                               │    status="executing"          │
 │                               │                               │    meta={work_dir, task_config}│
 │                               │                               │                                │
 │                               │                               │  mkdir work_dir/input_files/   │
 │                               │                               │  write task_config.json        │
 │                               │                               │                                │
 │                               │                               │  ×4 INSERT TaskStage           │
 │                               │                               ├───────────────────────────────►│
 │                               │                               │    stage_number=1..4           │
 │                               │                               │    status="pending"            │
 │                               │                               │                                │
 │                               │  ◄── { task_id, work_dir,     │                                │
 │                               │       stages: [4 pending] }   │                                │
 │                               │◄──────────────────────────────┤                                │
 │                               │                               │                                │
 │                               │  ─── TRIGGER STAGE 1 ──────► │                                │
```

---

## 2. Stage Execution Flow (Stages 1–4)

```
FRONTEND (useAIWeeklyTask)        BACKEND (routers/aiweekly.py)      PHASE ENGINE              DATABASE
 │                                   │                                │                          │
 │  POST /{id}/stages/{N}/execute    │                                │                          │
 │  { config_overrides: {model} }    │                                │                          │
 ├──────────────────────────────────►│                                │                          │
 │                                   │                                │                          │
 │                                   │  UPDATE TaskStage              │                          │
 │                                   │    status → "running"          │                          │
 │                                   ├─────────────────────────────────────────────────────────►│
 │                                   │                                │                          │
 │                                   │  asyncio.create_task(          │                          │
 │                                   │    _run_aiweekly_stage(...)    │                          │
 │                                   │  )                             │                          │
 │                                   │  ┌────────────────────────────►│                          │
 │  ◄── { status: "started" }        │  │                             │                          │
 │◄──────────────────────────────────┤  │                             │                          │
 │                                   │  │  BACKGROUND TASK:           │                          │
 │  Start console poll (2s)          │  │                             │                          │
 │  GET .../console?since=0          │  │  1. _build_shared_state()   │                          │
 ├──────────────────────────────────►│  │     merge prior stages      │                          │
 │                                   │  │                             │                          │
 │                                   │  │  2. Install console capture │                          │
 │                                   │  │     sys.stdout = capture    │                          │
 │                                   │  │                             │                          │
 │                                   │  │  3. _load_phase_class(N)    │                          │
 │                                   │  │     importlib → PhaseClass  │                          │
 │                                   │  │                             │                          │
 │                                   │  │  4. PhaseContext(task,       │                          │
 │                                   │  │       work_dir, shared)     │                          │
 │                                   │  │                             │                          │
 │                                   │  │  5. await phase.execute(ctx)│                          │
 │                                   │  │     ─────────────────────►  │                          │
 │                                   │  │                             │                          │
 │                                   │  │     ┌───────────────────────┴──────────────────────────┐
 │                                   │  │     │     PHASE PIPELINE (see §3 / §4 below)           │
 │                                   │  │     └───────────────────────┬──────────────────────────┘
 │                                   │  │                             │                          │
 │  ◄── console lines (polling)      │  │     ◄── PhaseResult        │                          │
 │◄──────────────────────────────────┤  │                             │                          │
 │                                   │  │                             │                          │
 │                                   │  │  6. Extract cost from result│                          │
 │                                   │  │     prompt_tokens,          │                          │
 │                                   │  │     completion_tokens       │                          │
 │                                   │  │     cost_usd                │                          │
 │                                   │  │                             │                          │
 │                                   │  │  7. INSERT CostRecord       │                          │
 │                                   │  │     run_id=task_id          │                          │
 │                                   │  │     model, tokens, cost_usd │                          │
 │                                   │  ├──────────────────────────────────────────────────────►│
 │                                   │  │                             │                          │
 │                                   │  │  8. UPDATE TaskStage        │                          │
 │                                   │  │     status → "completed"    │                          │
 │                                   │  │     output_data = {         │                          │
 │                                   │  │       shared: {key: text},  │                          │
 │                                   │  │       artifacts: {model},   │                          │
 │                                   │  │       cost: {tokens, usd}   │                          │
 │                                   │  │     }                       │                          │
 │                                   │  ├──────────────────────────────────────────────────────►│
 │                                   │  │                             │                          │
 │                                   │  │  9. If ALL 4 stages done:   │                          │
 │                                   │  │     WorkflowRun → completed │                          │
 │                                   │  │     _generate_cost_summary()│                          │
 │                                   │  │     → cost_summary.md       │                          │
 │                                   │  ├──────────────────────────────────────────────────────►│
 │                                   │  │                             │                          │
 │  Poll detects stage complete      │  │                             │                          │
 │  (GET /{id} → stage.status)       │  │                             │                          │
 │◄──────────────────────────────────┤  └──── cleanup: restore stdout │                          │
 │                                   │                                │                          │
 │  GET /{id}/stages/{N}/content     │                                │                          │
 ├──────────────────────────────────►│                                │                          │
 │  ◄── { content, field }           │                                │                          │
 │◄──────────────────────────────────┤                                │                          │
 │                                   │                                │                          │
 │  Display in editor panel          │                                │                          │
```

---

## 3. Stage 1 — Data Collection Pipeline (No LLM)

```
AIWeeklyCollectionPhase.execute(context)
 │
 │  Read task_config from shared_state:
 │    date_from, date_to, topics, sources
 │
 │  ┌──────────────────────────────────────────────────────────────────┐
 │  │  TOOL CALLS (direct Python, no LLM)                             │
 │  │                                                                  │
 │  │  1. collect_all_news(date_from, date_to, topics, sources)        │
 │  │     ├── RSS feeds (30+ sources: OpenAI, Google, Meta, etc.)     │
 │  │     ├── curated_ai_sources_search(limit=60)                     │
 │  │     ├── newsapi_search()        (if NEWSAPI_KEY set)            │
 │  │     ├── gnews_search()          (if GNEWS_API_KEY set)          │
 │  │     ├── prwire_search()         (press releases)                │
 │  │     └── multi_engine_web_search (DDG→Bing→Yahoo→Brave)          │
 │  │                                                                  │
 │  │  2. Per-company web searches for priority companies              │
 │  │     (openai, google, nvidia, meta, microsoft, etc.)             │
 │  │                                                                  │
 │  │  3. Date filtering: keep only items in [date_from, date_to]      │
 │  │                                                                  │
 │  │  4. Deduplication: by (url, title[:80])                           │
 │  └──────────────────────────────────────────────────────────────────┘
 │
 │  Output: raw_collection (markdown list of all collected items)
 │  Cost: $0.0000 (no LLM calls)
 │
 │  Save to: input_files/collection.json + collection.md
 │  Return PhaseResult with output_data = {
 │    "shared": { "raw_collection": content },
 │    "cost": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
 │  }
```

---

## 4. Stages 2–4 — LLM Pipeline (Inside `AIWeeklyPhaseBase.execute()`)

```
AIWeeklyPhaseBase.execute(context)
 │
 │  ┌─────────────────────────────────────────────────────────────┐
 │  │  A. BUILD PROMPTS                                           │
 │  │                                                             │
 │  │  system_prompt ← self.system_prompt (stage-specific)        │
 │  │  user_prompt   ← self.build_user_prompt(context)            │
 │  │                  └── Reads shared_state:                    │
 │  │                      Stage 2: raw_collection                │
 │  │                      Stage 3: curated_items                 │
 │  │                      Stage 4: draft_report                  │
 │  │                                                             │
 │  │  style_rule ← get_style_rule(context)                       │
 │  │               (concise/detailed/technical)                  │
 │  │  user_prompt += style_rule                                  │
 │  └─────────────────────────────────────────────────────────────┘
 │
 │  ┌─────────────────────────────────────────────────────────────┐
 │  │  B. TOKEN CAPACITY CHECK                                    │
 │  │                                                             │
 │  │  max_ctx, max_out = get_model_limits(model)                 │
 │  │  chunks = chunk_prompt_if_needed(system, user, model)       │
 │  │                                                             │
 │  │  Fits?  → single API call                                   │
 │  │  Overflows? → split at --- boundaries → multiple calls      │
 │  └─────────────────────────────────────────────────────────────┘
 │
 ▼
╔═════════════════════════════════════════════════════════════════╗
║  PASS 1: PRIMARY AGENT (Generation)                            ║
║                                                                ║
║  LLM Call #1                                                   ║
║  ┌───────────────────────────────────┐                         ║
║  │  system: Stage-specific persona   │                         ║
║  │  user:   Prior stage output +     │   ────►  LLM API       ║
║  │          style rule               │                         ║
║  │  model:  config.model             │   ◄────  draft content  ║
║  │  max_completion_tokens: dynamic   │                         ║
║  └───────────────────────────────────┘                         ║
╚════════════════════════════════╦════════════════════════════════╝
                                 │
                                 ▼
╔═════════════════════════════════════════════════════════════════╗
║  PASS 2: SPECIALIST AGENT (if multi_agent=True)                ║
║                                                                ║
║  LLM Call #2                                                   ║
║  ┌───────────────────────────────────┐                         ║
║  │  system: Specialist persona       │                         ║
║  │  user:   draft + validation       │   ────►  LLM API       ║
║  │          instructions             │                         ║
║  │  model:  specialist_model         │   ◄────  improved       ║
║  └───────────────────────────────────┘         content         ║
╚════════════════════════════════╦════════════════════════════════╝
                                 │
                                 ▼
╔═════════════════════════════════════════════════════════════════╗
║  PASS 3: REVIEWER AGENT (×n_reviews, default 1)               ║
║                                                                ║
║  LLM Call #3                                                   ║
║  ┌───────────────────────────────────┐                         ║
║  │  system: 11-point quality         │                         ║
║  │          checklist reviewer       │                         ║
║  │  user:   "Draft document:\n\n" +  │   ────►  LLM API       ║
║  │          content + style_rule     │                         ║
║  │  model:  review_model or same     │   ◄────  polished       ║
║  └───────────────────────────────────┘         content         ║
║                                                                ║
║  11-Point Review Checklist:                                    ║
║   1. Fix factual errors, weak analysis                         ║
║   2. Every item: date, source link, ≥100-word description      ║
║   3. Remove duplicates (each release once)                     ║
║   4. Verify 4-section structure                                ║
║   5. Replace placeholder text                                  ║
║   6. Professional executive tone                               ║
║   7. HALLUCINATION CHECK — remove untraceable items            ║
║   8. PRODUCT NAMES — remove invented names                     ║
║   9. DATE CHECK — remove unverifiable dates                    ║
║  10. METRIC CHECK — remove unverified stats                    ║
║  11. CLAIMS CHECK — strip unattributed superlatives            ║
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
│      "cost": {                                                  │
│        "prompt_tokens": X, "completion_tokens": Y,              │
│        "total_tokens": X+Y                                      │
│      }                                                          │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Shared State Accumulation Across Stages

```
Stage 1 executes (Data Collection — no LLM)
  │  Output: { "shared": { "raw_collection": "..." } }
  │  Cost: $0.0000
  ▼
Stage 2 reads shared_state = { raw_collection, task_config }
  │  Output: + curated_items
  │  LLM: 3 calls (primary+specialist+reviewer)
  ▼
Stage 3 reads shared_state = { raw_collection, curated_items, task_config }
  │  Output: + draft_report
  │  LLM: 3 calls
  ▼
Stage 4 reads shared_state = { raw_collection, curated_items, draft_report, task_config }
  │  Output: + final_report
  │  LLM: 2 calls (primary+reviewer, no specialist)
  ▼
ALL stages completed → WorkflowRun.status = "completed"
                     → _generate_cost_summary() → cost_summary.md
```

---

## 6. Database Entity Relationship

```
┌────────────────────────┐       ┌─────────────────────────┐
│     Session             │       │      WorkflowRun         │
├────────────────────────┤       ├─────────────────────────┤
│ id (PK)                │◄──────│ session_id (FK)          │
│ name                   │  1:N  │ id (PK) = task_id        │
│ status                 │       │ mode = "aiweekly"        │
│ mode = "aiweekly"      │       │ agent = "phase_orch..."  │
│ created_at             │       │ model                    │
└────────────────────────┘       │ status                   │
                                  │ task_description         │
                                  │ meta = {work_dir,        │
                                  │   task_config}           │
                                  │ started_at               │
                                  │ completed_at             │
                                  └───────┬─────────────────┘
                                          │ 1:N
                                          ▼
                              ┌─────────────────────────┐
                              │      TaskStage (×4)      │
                              ├─────────────────────────┤
                              │ id (PK)                  │
                              │ parent_run_id (FK)       │
                              │ stage_number (1–4)       │
                              │ stage_name               │
                              │ status                   │
                              │ output_data = {          │
                              │   shared: {key: content},│
                              │   artifacts: {model},    │
                              │   cost: {tokens, usd}   │
                              │ }                        │
                              │ error_message            │
                              └─────────────────────────┘

                              ┌─────────────────────────┐
                              │      CostRecord          │
                              ├─────────────────────────┤
                              │ id (PK)                  │
                              │ run_id (FK → WorkflowRun)│
                              │ session_id (FK)          │
                              │ model                    │
                              │ prompt_tokens            │
                              │ completion_tokens        │
                              │ total_tokens             │
                              │ cost_usd                 │
                              │ timestamp                │
                              └─────────────────────────┘
```

---

## 7. User Edit & Refinement Flow

```
USER                          FRONTEND                       BACKEND                        DATABASE
 │                               │                              │                              │
 │  Edit content in editor       │                              │                              │
 ├──────────────────────────────►│                              │                              │
 │                               │  PUT /{id}/stages/{N}/content│                              │
 │                               │  { content, field }          │                              │
 │                               ├─────────────────────────────►│                              │
 │                               │                              │  UPDATE TaskStage            │
 │                               │                              │    output_data.shared[field] │
 │                               │                              │  Write to input_files/{file} │
 │                               │                              ├─────────────────────────────►│
 │                               │  ◄── { status: "saved" }     │                              │
 │                               │◄─────────────────────────────┤                              │
 │                               │                              │                              │
 │  Type refinement instruction  │                              │                              │
 ├──────────────────────────────►│                              │                              │
 │                               │  POST /{id}/stages/{N}/refine                               │
 │                               │  { message, content }        │                              │
 │                               ├─────────────────────────────►│                              │
 │                               │                              │  safe_completion()           │
 │                               │                              │  (system: AI news editor)    │
 │                               │                              │  ────────► LLM API           │
 │                               │                              │  ◄──────── refined content   │
 │                               │  ◄── { refined_content }     │                              │
 │                               │◄─────────────────────────────┤                              │
 │  See refined content          │                              │                              │
 │◄──────────────────────────────┤                              │                              │
```

---

## 8. Task Resumption Flow

```
USER                          FRONTEND                       BACKEND
 │                               │                              │
 │  Open AI Weekly page          │                              │
 │                               │  GET /api/aiweekly/recent    │
 │                               ├─────────────────────────────►│
 │                               │  ◄── [{task_id, progress}]   │
 │                               │◄─────────────────────────────┤
 │                               │                              │
 │  See "In Progress" cards      │                              │
 │  Click Resume arrow           │                              │
 ├──────────────────────────────►│                              │
 │                               │  GET /api/aiweekly/{id}      │
 │                               ├─────────────────────────────►│
 │                               │  ◄── full task state         │
 │                               │◄─────────────────────────────┤
 │                               │                              │
 │  Wizard jumps to correct step │                              │
 │  (last completed + 1)         │                              │
 │◄──────────────────────────────┤                              │
```

---

## 9. Stop, Reset & Delete Flows

### Stop (Cancel Running Stage)

```
USER → POST /api/aiweekly/{id}/stop
         │
         ├── Cancel asyncio tasks
         ├── UPDATE running TaskStages → "failed" ("Stopped by user")
         └── UPDATE WorkflowRun → "failed"
```

### Reset from Stage N

```
USER → POST /api/aiweekly/{id}/reset-from/{N}
         │
         └── UPDATE TaskStage[N..4] → "pending", clear output_data
```

### Delete Task

```
USER → DELETE /api/aiweekly/{id}
         │
         ├── DELETE WorkflowRun (CASCADE → TaskStages, CostRecords)
         └── shutil.rmtree(work_dir)
```

---

## 10. Cost Tracking Flow

```
PHASE ENGINE                          BACKEND                          DATABASE
 │                                       │                                │
 │  LLM calls return:                    │                                │
 │    usage.prompt_tokens = 5000         │                                │
 │    usage.completion_tokens = 3000     │                                │
 │                                       │                                │
 │  PhaseResult.output_data["cost"] = {  │                                │
 │    "prompt_tokens": 5000,             │                                │
 │    "completion_tokens": 3000,         │                                │
 │    "total_tokens": 8000               │                                │
 │  }                                    │                                │
 ├──────────────────────────────────────►│                                │
 │                                       │  cost_usd = (5000 × 0.002     │
 │                                       │           + 3000 × 0.008)     │
 │                                       │           / 1000              │
 │                                       │         = $0.034              │
 │                                       │                                │
 │                                       │  INSERT CostRecord            │
 │                                       │    run_id = task_id            │
 │                                       │    model = "gpt-4.1"          │
 │                                       │    prompt_tokens = 5000       │
 │                                       │    completion_tokens = 3000   │
 │                                       │    cost_usd = 0.034           │
 │                                       ├───────────────────────────────►│
 │                                       │                                │
 │                                       │  Store in output_data["cost"]  │
 │                                       │    cost_usd = 0.034           │
 │                                       ├───────────────────────────────►│
 │                                       │                                │
 ═══ ALL 4 STAGES COMPLETED ═══          │                                │
                                         │                                │
                                         │  _generate_cost_summary()      │
                                         │    Read each TaskStage's       │
                                         │    output_data["cost"]          │
                                         │                                │
                                         │  Write cost_summary.md:        │
                                         │  ┌────────────────────────────┐│
                                         │  │ # AI Weekly — Cost Summary ││
                                         │  │ ## Per-Stage Breakdown     ││
                                         │  │ | # | Stage | Model | ... ││
                                         │  │ |---|-------|-------|-----││
                                         │  │ | 1 | Data Collection |..0││
                                         │  │ | 2 | Content Curation|.. ││
                                         │  │ | 3 | Report Gen.     |.. ││
                                         │  │ | 4 | Quality Review  |.. ││
                                         │  │ |   | **TOTAL**       |.. ││
                                         │  │ ## Summary                ││
                                         │  │ - Total Cost: $X.XXXX     ││
                                         │  └────────────────────────────┘│
                                         │  → input_files/cost_summary.md │
                                         │                                │
 ═══ FRONTEND QUERIES COST ═══           │                                │
                                         │                                │
 GET /api/aiweekly/{id}                  │                                │
 ────────────────────────────────────────►│                                │
                                         │  Aggregate cost from all       │
                                         │  stages' output_data["cost"]   │
                                         │                                │
 ◄── { total_cost: { prompt_tokens,      │                                │
       completion_tokens, total_tokens }} │                                │
 ◄───────────────────────────────────────┤                                │

 GET /api/aiweekly/{id}/download/cost_summary.md
 ────────────────────────────────────────►│
                                         │  FileResponse(cost_summary.md) │
 ◄── cost_summary.md file                │                                │
 ◄───────────────────────────────────────┤                                │
```

---

## 11. Complete End-to-End User Journey

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                             │
│   ① SETUP (Step 0)                                                                         │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • See "In Progress" cards (if any, scrollable >5)   │                                   │
│   │  • Pick date range (From / To)                      │                                   │
│   │  • Select topics (LLM, CV, Robotics, etc.)          │                                   │
│   │  • Select sources (RSS, NewsAPI, GNews, etc.)       │                                   │
│   │  • Choose style (Concise / Detailed / Technical)    │                                   │
│   │  • Model settings (gear icon)                       │                                   │
│   │  • Click "Collect Data" ────────────────────────────┼──► Creates task + 4 stages in DB  │
│   └─────────────────────────────────────────────────────┘    Triggers Stage 1 execution     │
│       │                                                                                     │
│       ▼                                                                                     │
│   ② DATA COLLECTION (Step 1)                                                               │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • No LLM — direct Python tool calls                │                                   │
│   │  • Console: "RSS/openai: 12 items", etc.            │                                   │
│   │  • Collects from 30+ RSS feeds, APIs, web search    │                                   │
│   │  • Date filter + deduplication                      │                                   │
│   │  • Output: collection.md                            │                                   │
│   │  • Editor shows collected items                     │                                   │
│   │  • Click "Next" → triggers Stage 2 ────────────────┼──► Saves edits + executes next    │
│   └─────────────────────────────────────────────────────┘                                   │
│       │                                                                                     │
│       ▼                                                                                     │
│   ③ CONTENT CURATION (Step 2)                                                              │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • 3 LLM calls: Primary → Specialist → Reviewer     │                                   │
│   │  • Filters noise, ranks by relevance                │                                   │
│   │  • Output: curated.md                               │                                   │
│   │  • Editor + refinement chat                         │                                   │
│   │  • Click "Next" ───────────────────────────────────►│                                   │
│   └─────────────────────────────────────────────────────┘                                   │
│       │                                                                                     │
│       ▼                                                                                     │
│   ④ REPORT GENERATION (Step 3)                                                             │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • 3 LLM calls: builds 4-section report             │                                   │
│   │  • Executive Summary, Key Highlights, Trends, Table │                                   │
│   │  • Output: report_draft.md                          │                                   │
│   │  • Editor + refinement chat                         │                                   │
│   │  • Click "Next" ───────────────────────────────────►│                                   │
│   └─────────────────────────────────────────────────────┘                                   │
│       │                                                                                     │
│       ▼                                                                                     │
│   ⑤ QUALITY REVIEW (Step 4)                                                                │
│   ┌─────────────────────────────────────────────────────┐                                   │
│   │  • 2 LLM calls: polishes to publication quality     │                                   │
│   │  • Hallucination check, fact verification            │                                   │
│   │  • Output: report_final.md                          │                                   │
│   │  • Auto-generate cost_summary.md                    │                                   │
│   │  • Download: MD + PDF + all 4 artifacts + cost      │                                   │
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

## 12. Session & Database Lifecycle Summary

```
TIME ──────────────────────────────────────────────────────────────────────────────────►

TASK CREATION:
  ┌──────────┐   ┌──────────────┐   ┌────────────┐
  │ Session   │   │ WorkflowRun  │   │ ×4 TaskStage│
  │ (active)  │   │ (executing)  │   │ (pending)   │
  └──────────┘   └──────────────┘   └────────────┘

STAGE 1 EXECUTE:
  TaskStage[1] → "running" ───► CollectionPhase.execute() (no LLM, tools only)
                                    └── TaskStage[1] → "completed"

STAGE 2 EXECUTE:
  _build_shared_state(task, up_to=2) → reads TaskStage[1].output_data
  TaskStage[2] → "running" ───► CurationPhase.execute() (3 LLM calls)
                                    ├── CostRecord INSERT
                                    └── TaskStage[2] → "completed"

STAGE 3 EXECUTE:
  _build_shared_state(task, up_to=3) → reads TaskStage[1-2].output_data
  TaskStage[3] → "running" ───► GenerationPhase.execute() (3 LLM calls)
                                    ├── CostRecord INSERT
                                    └── TaskStage[3] → "completed"

STAGE 4 EXECUTE:
  _build_shared_state(task, up_to=4) → reads ALL TaskStage[1-3].output_data
  TaskStage[4] → "running" ───► ReviewPhase.execute() (3 LLM calls)
                                    ├── CostRecord INSERT
                                    └── TaskStage[4] → "completed"

  ALL 4 completed? → WorkflowRun → "completed", completed_at = now()
                   → _generate_cost_summary() → cost_summary.md


USER EDITS (any time after stage completes):
  PUT /stages/{N}/content → UPDATE TaskStage[N].output_data["shared"][key]
                          → Write to {stage}.md file on disk

REFINEMENT CHAT (any time after stage completes):
  POST /stages/{N}/refine → LLM call → refined content

RESET FROM STAGE N:
  TaskStage[N..4] → "pending", clear output_data

STOP:
  Cancel asyncio tasks → TaskStages → "failed" → WorkflowRun → "failed"

DELETE:
  WorkflowRun DELETE (CASCADE → all TaskStages + CostRecords)
  shutil.rmtree(work_dir)
```

---

## 13. API Endpoint Quick Reference

| # | Method | Path | Body | Response | DB Effect |
|---|--------|------|------|----------|-----------|
| 1 | POST | `/api/aiweekly/create` | `{date_from, date_to, topics, sources, style}` | `{task_id, work_dir, stages[]}` | INSERT Session + WorkflowRun + 4 TaskStages |
| 2 | GET | `/api/aiweekly/recent` | — | `[{task_id, task, status, progress}]` | SELECT WorkflowRun WHERE status in executing/draft |
| 3 | GET | `/api/aiweekly/{id}` | — | `{task_id, stages, progress, total_cost}` | SELECT WorkflowRun + TaskStages, aggregate cost |
| 4 | POST | `/api/aiweekly/{id}/stages/{N}/execute` | `{config_overrides?}` | `{status: "started"}` | UPDATE TaskStage → "running", spawns async task |
| 5 | GET | `/api/aiweekly/{id}/stages/{N}/content` | — | `{content, field}` | SELECT TaskStage.output_data |
| 6 | PUT | `/api/aiweekly/{id}/stages/{N}/content` | `{content, field}` | `{status: "saved"}` | UPDATE TaskStage.output_data["shared"] |
| 7 | POST | `/api/aiweekly/{id}/stages/{N}/refine` | `{message, content}` | `{refined_content}` | LLM call only (no DB write) |
| 8 | GET | `/api/aiweekly/{id}/stages/{N}/console` | `?since=idx` | `{lines[], next_index}` | READ _console_buffers (in-memory) |
| 9 | POST | `/api/aiweekly/{id}/reset-from/{N}` | — | `{status: "reset"}` | UPDATE TaskStages[N..4] → "pending" |
| 10 | POST | `/api/aiweekly/{id}/stop` | — | `{status: "stopped"}` | TaskStages → "failed", WorkflowRun → "failed" |
| 11 | GET | `/api/aiweekly/{id}/download/{file}` | — | FileResponse | READ file from disk |
| 12 | GET | `/api/aiweekly/{id}/download-pdf/{file}` | — | FileResponse (PDF) | Convert MD → PDF + serve |
| 13 | DELETE | `/api/aiweekly/{id}` | — | `{status: "deleted"}` | DELETE WorkflowRun (CASCADE) + rmtree |

---

## 14. Output Files

```
{work_dir}/input_files/
├── task_config.json       # User configuration (date range, topics, sources, style)
├── collection.json        # Stage 1 output: structured JSON of all collected items
├── collection.md          # Stage 1 output: markdown summary of collected items
├── curated.md             # Stage 2 output: LLM-curated items
├── report_draft.md        # Stage 3 output: draft report
├── report_final.md        # Stage 4 output: final publication-ready report
└── cost_summary.md        # Auto-generated cost breakdown (per-stage + total)
```
