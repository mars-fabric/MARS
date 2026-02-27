# Product Discovery Assistant (PDA) — Integration Guide

This document describes how the PDA frontend was extracted from the standalone `pda_6d3220af/` Vite app and integrated into the unified `cmbagent-ui` Next.js frontend, backed by the MARS FastAPI backend using **cmbagent** for AI generation.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   cmbagent-ui (Next.js)                  │
│                                                         │
│  Tasks Page ─► ProductDiscoveryTask (9-step wizard)     │
│                     │                                   │
│                     ▼                                   │
│              lib/pda-api.ts                             │
│          (fetch → /api/pda/*)                           │
└────────────────────┬────────────────────────────────────┘
                     │  HTTP (localhost:8000)
┌────────────────────▼────────────────────────────────────┐
│              MARS FastAPI Backend                        │
│                                                         │
│  routers/pda.py  ──►  services/pda_service.py           │
│   (10 endpoints)       │                                │
│                        └─ create_openai_client()         │
│                            (All steps: reliable LLM)    │
└─────────────────────────────────────────────────────────┘
```

---

## What Was Done

### Phase 1 — Backend (FastAPI)

Replaced direct LLM API calls (`https://icets-pde.ad.infosys.com/tools/openai/v1/chat/completions`) with cmbagent-powered generation.

#### Files Created

| File | Purpose |
|------|---------|
| `backend/services/pda_service.py` | Core service layer — all steps use `create_openai_client()` for reliable JSON generation via cmbagent's provider auto-detection (OpenAI / Azure / Anthropic / Gemini). |
| `backend/routers/pda.py` | FastAPI router — 10 REST endpoints under `/api/pda/` with graceful error handling |

#### Files Modified

| File | Change |
|------|--------|
| `backend/routers/__init__.py` | Registered `pda_router` via `app.include_router(pda_router)` |

#### Backend Endpoints

| Method | Path | Step | Strategy |
|--------|------|------|----------|
| `GET` | `/api/pda/health` | — | Health check |
| `POST` | `/api/pda/client-details` | 0 | `create_openai_client()` |
| `POST` | `/api/pda/research-summary` | 1 | `create_openai_client()` |
| `POST` | `/api/pda/problem-definition` | 2 | `create_openai_client()` |
| `POST` | `/api/pda/opportunities` | 3 | `create_openai_client()` |
| `POST` | `/api/pda/solution-archetypes` | 4 | `create_openai_client()` |
| `POST` | `/api/pda/features` | 5 | `create_openai_client()` |
| `POST` | `/api/pda/prompts` | 6 | `create_openai_client()` |
| `POST` | `/api/pda/slide-content` | 7 | `create_openai_client()` |
| `POST` | `/api/pda/deep-research` | — | `cmbagent` Planning & Control |

---

### Phase 2 — Frontend (cmbagent-ui)

Extracted the full PDA 9-step wizard UI from `pda_6d3220af/` (React + Vite + shadcn/ui) and rewrote it as a single task component within `cmbagent-ui` (Next.js + MARS design tokens).

#### Files Created

| File | Purpose |
|------|---------|
| `cmbagent-ui/types/pda.ts` | TypeScript type definitions (`IntakeFormData`, `ResearchSummary`, `ProblemDefinition`, `OpportunityArea`, `SolutionArchetype`, `Feature`, `DiscoveryState`) |
| `cmbagent-ui/lib/pda-api.ts` | API service — 8 exported functions calling `/api/pda/*` via `getApiUrl()` from `lib/config.ts` |
| `cmbagent-ui/components/tasks/ProductDiscoveryTask.tsx` | Complete 9-step wizard component (~1500 lines) with all step sub-components inlined |

#### Files Modified

| File | Change |
|------|--------|
| `cmbagent-ui/components/tasks/TaskList.tsx` | Added `product-discovery` entry to `TASKS` array (Compass icon, cyan-to-blue gradient) |
| `cmbagent-ui/app/tasks/page.tsx` | Added `'product-discovery'` to `ActiveTask` type union; added routing to `ProductDiscoveryTask` |

---

## PDA Wizard — 9 Steps

| Step | Name | Component | What It Does |
|------|------|-----------|--------------|
| 0 | **Intake** | `IntakeStep` | Form: client name (auto-detects industry), business function, discovery type, problem keywords, expected outputs |
| 1 | **Research** | `ResearchStep` | Auto-generates research via direct LLM: market trends, competitor moves, pain points, workshop angles, references |
| 2 | **Problem** | `ProblemStep` | Generates structured problem definition: statement, supporting points, personas, KPIs, root cause, reframing examples |
| 3 | **Opportunity** | `OpportunityStep` | Generates 4 opportunity cards (Revenue/Efficiency/Experience/Risk); user selects one |
| 4 | **Solution** | `SolutionStep` | Generates solution archetypes for selected opportunity; user selects one |
| 5 | **Features** | `FeatureStep` | Generates feature set grouped by bucket; user checks/unchecks features, can add custom ones |
| 6 | **Prompts** | `PromptStep` | Generates platform-specific prompts (Lovable, Google AI Studio, General LLM) with copy buttons |
| 7 | **Slides** | `SlideStep` | Generates presentation slide content in Markdown; parsed into individual slide cards |
| 8 | **Summary** | `SummaryStep` | Shows overview, copy buttons for each artifact, download-as-Markdown option |

---

## Key Design Decisions

### 1. MARS Design Tokens (not shadcn/ui)

The original PDA used shadcn/ui components (`Card`, `Button`, `Input`, `Select`, etc.). These were replaced with:
- Native HTML elements (`<input>`, `<select>`, `<textarea>`, `<button>`)
- MARS CSS variables for theming (`--mars-color-primary`, `--mars-color-surface`, `--mars-color-border`, etc.)
- A lightweight `Card` wrapper component styled with MARS tokens
- The `Button` import from `@/components/core` (existing MARS component)

### 2. Single-File Component

All 9 step components are inlined in `ProductDiscoveryTask.tsx` rather than split into separate files. This keeps the integration self-contained and easy to navigate. Shared UI primitives (`CollapsibleSection`, `StepHeader`, `DetailList`, `Field`, `Card`, `Md`) are defined at the bottom of the file.

### 3. API Service Layer

`lib/pda-api.ts` mirrors the original `pda_6d3220af/src/lib/llm-service.ts` but uses:
- `getApiUrl()` from `lib/config.ts` (resolves to `http://localhost:8000` in dev)
- Standard `fetch()` (works in Next.js without Vite proxy)
- Same function signatures for drop-in compatibility

### 4. State Persistence

Discovery state is persisted to `localStorage` under the key `pda-discovery-state` — same pattern as the original app but with a different key to avoid conflicts.

### 5. Notification System

Replaced `sonner` toast library with a minimal DOM-based `notify()` function to avoid adding a dependency. Can be upgraded to a proper toast library later.

---

## How to Run

### 1. Start the Backend

```bash
cd /home/sachin_mourya/Desktop/MARS
source .venv/bin/activate
cd backend
python run.py
```

The backend starts on `http://localhost:8000`. Verify PDA endpoints:
```bash
curl http://localhost:8000/api/pda/health
# → {"status":"ok","service":"pda"}
```

### 2. Start the Frontend

```bash
cd /home/sachin_mourya/Desktop/MARS/cmbagent-ui
npm run dev
```

The frontend starts on `http://localhost:3000`.

### 3. Access PDA

1. Open `http://localhost:3000`
2. Click **Tasks** in the left sidebar
3. Click the **Product Discovery** task card
4. Fill in the Intake form and click **Start Discovery**
5. Follow the 9-step wizard — each step auto-generates content via the backend

---

## File Tree (PDA-related only)

```
MARS/
├── backend/
│   ├── routers/
│   │   ├── __init__.py          # includes pda_router
│   │   └── pda.py               # 10 REST endpoints
│   └── services/
│       └── pda_service.py       # cmbagent + openai client logic
│
├── cmbagent-ui/
│   ├── app/tasks/
│   │   └── page.tsx             # routes 'product-discovery' → component
│   ├── components/tasks/
│   │   ├── TaskList.tsx          # TASKS array includes product-discovery
│   │   └── ProductDiscoveryTask.tsx  # 9-step wizard (~1500 lines)
│   ├── lib/
│   │   └── pda-api.ts           # API service (8 functions)
│   └── types/
│       └── pda.ts               # TypeScript interfaces
│
└── pda_6d3220af/                # ← NO LONGER NEEDED (legacy standalone app)
```

---

## Migration Mapping

| Original (pda_6d3220af) | New (cmbagent-ui) |
|---|---|
| `src/types/discovery.ts` | `types/pda.ts` |
| `src/lib/llm-service.ts` | `lib/pda-api.ts` |
| `src/pages/Index.tsx` | `components/tasks/ProductDiscoveryTask.tsx` (main component + state) |
| `src/components/steps/IntakeForm.tsx` | `IntakeStep` (inlined) |
| `src/components/steps/ResearchSummary.tsx` | `ResearchStep` (inlined) |
| `src/components/steps/ProblemDefinition.tsx` | `ProblemStep` (inlined) |
| `src/components/steps/OpportunityAreas.tsx` | `OpportunityStep` (inlined) |
| `src/components/steps/SolutionArchetypes.tsx` | `SolutionStep` (inlined) |
| `src/components/steps/FeatureSetBuilder.tsx` | `FeatureStep` (inlined) |
| `src/components/steps/PromptGenerator.tsx` | `PromptStep` (inlined) |
| `src/components/steps/SlideGenerator.tsx` | `SlideStep` (inlined) |
| `src/components/steps/Summary.tsx` | `SummaryStep` (inlined) |
| `src/components/StepIndicator.tsx` | `StepIndicatorBar` (inlined) |
| `src/components/StepNavigation.tsx` | Bottom nav in main component |
| `src/components/EditableContent.tsx` | Removed (content displayed read-only via `Md`) |
| `src/components/MarkdownRenderer.tsx` | `renderMarkdown()` + `Md` component (inlined) |
| shadcn/ui components | MARS CSS variables + native HTML elements |
| `sonner` toasts | `notify()` helper (DOM-based) |
| Vite proxy (`/api → :8000`) | `getApiUrl()` from `lib/config.ts` (direct URL) |
| `localStorage` key `discovery-state` | `localStorage` key `pda-discovery-state` |

---

## Reliability & Error Handling

### LLM Call Strategy

All steps use `create_openai_client()` via cmbagent's provider auto-detection for **reliable, direct LLM calls**.

Note: `cmbagent.one_shot(agent='researcher')` was initially used for web-search-augmented research but it consistently fails due to an autogen message-management bug (`IndexError` in `generate_function_call_reply` after message removal). All steps now use direct LLM calls for reliability.

### Error Resilience

| Layer | Mechanism |
|-------|-----------|
| `_call_llm_direct()` | Retries up to 2 times with exponential back-off |
| `generate_research_summary()` | Direct LLM call with JSON extraction; wraps raw text as last resort |
| Router (Steps 1-2) | Returns degraded 200 response (with error message in data) instead of 500 |
| Router (Steps 3-7) | Returns 500 with descriptive error message |
| Frontend | All steps wrapped in try/catch with user-visible error notifications |
