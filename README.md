<p align="center">
  <h1 align="center">MARS</h1>
  <p align="center"><strong>Multi-Agent Research System</strong></p>
  <p align="center">
    Turn complex work into automated, multi-agent workflows.<br/>
    From market insights to research papers — define a task, pick a mode, let the agents deliver.
  </p>
</p>

<p align="center">
  <a href="#-modes">Modes</a> &nbsp;&bull;&nbsp;
  <a href="#-tasks">Tasks</a> &nbsp;&bull;&nbsp;
  <a href="#-what-you-can-build">Use Cases</a> &nbsp;&bull;&nbsp;
  <a href="#-getting-started">Getting Started</a> &nbsp;&bull;&nbsp;
  <a href="#-architecture">Architecture</a>
</p>

<br/>

> **MARS** orchestrates **50+ specialized AI agents** — planners, coders, researchers, reviewers, web surfers, OCR processors — powered by [AG2](https://github.com/ag2ai/ag2) (AutoGen 2). Give it a task, choose how agents should work (the _mode_), and get back deliverables: reports, code reviews, research papers, product strategies, weekly briefings, or anything you can define.

<br/>

## Why MARS?

Complex work involves too many steps — gathering information, analyzing data, writing reports, iterating on feedback. MARS handles the heavy lifting so you can focus on decisions that matter.

<table>
<tr>
<td width="50%">

**8 composable modes**
Single-pass, multi-step planning, hypothesis generation, document extraction, literature review, input enrichment, human-in-the-loop, copilot. Mix and match to build any workflow.

</td>
<td width="50%">

**50+ specialized agents**
Planning, coding, web search, literature retrieval, critical evaluation, and document processing — orchestrated in pipelines that carry context across every phase.

</td>
</tr>
<tr>
<td>

**Pre-built tasks, unlimited custom ones**
Ship with templates for deep research, AI weekly reports, code review, product discovery, and release notes. Build your own with the Task Builder.

</td>
<td>

**Human-in-the-loop or fully autonomous**
Review and approve agent plans at every step, or let MARS run end-to-end on its own. Your choice, per task.

</td>
</tr>
</table>

<br/>

---

<br/>

## 🔀 Modes

Modes define _how_ agents approach a task. They are the building blocks — combine any mode with different agents and configurations to create unlimited automated workflows.

<br/>

<table>
<tr>
<td><strong>Mode</strong></td>
<td><strong>What It Does</strong></td>
<td><strong>Good For</strong></td>
</tr>

<tr>
<td>

**Single-Pass Analysis**<br/>`one-shot`

</td>
<td>One agent, one pass, no iterative planning. Fast and direct.</td>
<td>Quick analysis, code gen, report drafts, release notes, one-off scripts</td>
</tr>

<tr>
<td>

**Multi-Step Research**<br/>`planning-control`

</td>
<td>Planner creates a plan, reviewer validates, execution agents carry it out step by step with context across phases.</td>
<td>Market research, competitive intelligence, technical investigations, multi-part analyses</td>
</tr>

<tr>
<td>

**Hypothesis Generation**<br/>`idea-generation`

</td>
<td><code>idea_maker</code> proposes, <code>idea_hater</code> critiques — adversarial loop that stress-tests ideas before you commit.</td>
<td>Product brainstorming, strategic planning, research directions, design exploration</td>
</tr>

<tr>
<td>

**Document Extraction**<br/>`ocr`

</td>
<td>Mistral OCR extracts structured text from PDFs, scans, handwritten notes, and figures.</td>
<td>Digitizing documents, extracting tables from reports, processing scanned records</td>
</tr>

<tr>
<td>

**Literature Review**<br/>`arxiv`

</td>
<td>Downloads papers, extracts content, summarizes findings and citations.</td>
<td>Lit reviews, finding related work, surveying a field, annotated bibliographies</td>
</tr>

<tr>
<td>

**Input Enrichment**<br/>`enhance-input`

</td>
<td>Auto-downloads referenced documents, runs OCR and summarization, enriches your input before agents start working.</td>
<td>Tasks with external references, multi-source context, pre-processing for deeper analysis</td>
</tr>

<tr>
<td>

**Human-in-the-Loop**<br/>`hitl-interactive`

</td>
<td>Approval checkpoints at every decision point. Agents propose, you approve, then they execute.</td>
<td>High-stakes work, expert-guided analysis, exploratory research, full-control workflows</td>
</tr>

<tr>
<td>

**Copilot Chat**<br/>`copilot`

</td>
<td>Conversational interface with persistent context. Ask follow-ups, redirect, iterate in real time.</td>
<td>Exploratory analysis, iterative problem-solving, rapid prototyping, guided sessions</td>
</tr>
</table>

<br/>

<details>
<summary><strong>Copilot workflow presets</strong></summary>
<br/>

| Preset | Behavior |
|--------|----------|
| **Copilot Assistant** | Adapts to complexity. Plans when needed, asks approval after each step. |
| **Interactive Session** | Continuous back-and-forth. Up to 50 turns. |
| **Quick Task** | Direct execution. No planning, no approval. |
| **Interactive Copilot** | Proposes actions first, waits for your input before executing. |

</details>

<br/>

---

<br/>

## 📋 Tasks

Tasks are where modes become **deliverables**. Each task = a mode + agents + configuration = a specific output. MARS ships with pre-built templates, and the Task Builder lets you create as many custom ones as you need.

<br/>

### Pre-Built Templates

<table>
<tr>
<td width="20%"><strong>Deep Scientific Research</strong></td>
<td width="20%"><code>deep-research</code></td>
<td>4-stage pipeline: idea generation → method development → experiments → LaTeX paper. Adversarial review built in. Review and refine between every stage.</td>
</tr>
<tr>
<td><strong>AI Weekly Report</strong></td>
<td><code>hitl-interactive</code></td>
<td>Weekly technology briefings with human approval at each step. Planner outlines, researcher gathers, engineer compiles.</td>
</tr>
<tr>
<td><strong>Code Review</strong></td>
<td><code>planning-control</code></td>
<td>Multi-dimensional code analysis: correctness, performance, security, style. Plans review strategy first, then executes.</td>
</tr>
<tr>
<td><strong>Release Notes</strong></td>
<td><code>one-shot</code></td>
<td>Reads Git history, categorizes changes, produces readable release documentation.</td>
</tr>
<tr>
<td><strong>Product Discovery</strong></td>
<td><code>one-shot</code></td>
<td>Full workshop flow: client analysis → problem definition → opportunities → solutions → features → builder prompts.</td>
</tr>
</table>

<br/>

### Build Your Own

The modes are building blocks. Combine any mode + agent set + config to automate whatever you need:

| Task Idea | Mode | Deliverable |
|-----------|------|-------------|
| Competitive Landscape Report | `planning-control` | Structured competitor comparison |
| Patent Prior Art Search | `arxiv` + `enhance-input` | Summarized prior art from publications |
| Technical Due Diligence | `hitl-interactive` | Codebase/system analysis with checkpoints |
| Weekly Market Digest | `hitl-interactive` | Recurring market trend briefings |
| Research Paper | `deep-research` | Full LaTeX paper from idea to PDF |
| Onboarding Guide Generator | `one-shot` | Repo documentation for new team members |
| Customer Feedback Synthesis | `idea-generation` | Ranked hypotheses about user pain points |

<br/>

**Task Builder** lets you configure:

```
Task Name       →  What you want done
Execution Mode  →  Any of the 8 modes
Model           →  GPT-4o, Claude, Gemini, etc.
Max Rounds      →  1–100 agent turns
Approval Mode   →  none | always | on-failure
```

<br/>

---

<br/>

## 🚀 What You Can Build

<table>
<tr>
<td width="50%">

### Automate Recurring Deliverables
Weekly reports, market digests, release notes, competitive updates — set up once, run on demand. Same multi-agent pipeline, consistent output every time.

### Generate Market Insights
Multi-Step Research mode + web search + doc retrieval. Planner breaks work into phases, researchers gather data, engineer compiles the final report.

### Run Product Discovery
Automate the entire workshop — client analysis, problem definition, opportunities, solutions, features. Start with the template, iterate with Copilot.

### Write Research Papers
Idea → adversarial review → methodology → experiments → compiled LaTeX PDF. Review and refine between every stage of the Deep Research pipeline.

</td>
<td width="50%">

### Literature Discovery & Synthesis
Agents search ArXiv, download papers, OCR content, build vector stores. Describe your question, get a structured synthesis.

### Build Reproducible Pipelines
`engineer` and `executor` agents run code in sandboxed environments. Every execution tracked with costs, files, and event logs. Re-run with different inputs.

### Extend With Your Own Tools
Pluggable integrations via CrewAI and LangChain. Add domain-specific tools without touching core code. Pre-load RAG agents with your data.

### Collaborate Interactively
Copilot mode for real-time pair-work. Sessions persist context across turns. Multi-step mode carries context across phases — nothing lost.

</td>
</tr>
</table>

<br/>

---

<br/>

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (UI)                     │
│          Next.js 14  ·  React 18  ·  TailwindCSS    │
│        Real-time via Socket.IO  ·  DAG Visualizer   │
├─────────────────────────────────────────────────────┤
│                   Backend (API)                      │
│            FastAPI  ·  Uvicorn  ·  WebSockets        │
│     REST endpoints  ·  Task engine  ·  Event stream  │
├─────────────────────────────────────────────────────┤
│               Agent Framework (Core)                 │
│              AG2 multi-agent orchestration            │
│      50+ agents  ·  DAG execution  ·  RAG pipeline   │
├─────────────────────────────────────────────────────┤
│                  Storage & Data                      │
│         SQLAlchemy (SQLite / PostgreSQL)  ·  Alembic │
│        File tracking  ·  Cost records  ·  Events     │
└─────────────────────────────────────────────────────┘
```

<br/>

### Tech Stack

| Layer | Technology | Purpose |
|:------|:-----------|:--------|
| Frontend | Next.js 14, React 18, TailwindCSS | Web UI with real-time updates |
| Backend | FastAPI, Uvicorn | REST API + WebSocket server |
| Agents | AG2 (AutoGen 2) | Multi-agent orchestration |
| Real-Time | WebSockets, Socket.IO | Live task streaming |
| Database | SQLAlchemy, SQLite / PostgreSQL | Persistence and tracking |
| DAG Viz | @xyflow/react | Interactive graph rendering |
| Tools | CrewAI, LangChain | External tool integrations |
| Deploy | Docker, Docker Compose | Containerized deployment |

<br/>

---

<br/>

## 🤖 Agent System

50+ agents organized by function:

<table>
<tr>
<td valign="top" width="25%">

**Planning**
| Agent | Role |
|:------|:-----|
| `planner` | Plans and breakdowns |
| `task_improver` | Refines descriptions |
| `plan_recorder` | Persists plans |
| `plan_reviewer` | Quality review |
| `plan_setter` | Activates plans |

</td>
<td valign="top" width="25%">

**Execution**
| Agent | Role |
|:------|:-----|
| `engineer` | Writes code |
| `researcher` | Research & analysis |
| `executor` | Sandboxed code run |
| `executor_bash` | Shell commands |
| `installer` | Package installs |

</td>
<td valign="top" width="25%">

**Retrieval**
| Agent | Role |
|:------|:-----|
| `rag_agents` | RAG pipelines |
| `retrieve_assistant` | Doc retrieval |
| `web_surfer` | Web browsing |
| `perplexity` | AI search |

</td>
<td valign="top" width="25%">

**Utility**
| Agent | Role |
|:------|:-----|
| `idea_maker` | Generates ideas |
| `idea_hater` | Critiques ideas |
| `summarizer` | Summarizes output |
| `terminator` | Task completion |
| `copilot_control` | Copilot flow |

</td>
</tr>
</table>

<br/>

---

<br/>

## 🏁 Getting Started

### Prerequisites

- **Python** >= 3.12 &nbsp;&nbsp;|&nbsp;&nbsp; **Node.js** >= 18 &nbsp;&nbsp;|&nbsp;&nbsp; **npm** >= 9 &nbsp;&nbsp;|&nbsp;&nbsp; **Git**
- At least one LLM API key (OpenAI, Anthropic, Gemini, etc.)

### Install

```bash
git clone https://github.com/CMBAgents/cmbagent.git && cd cmbagent

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -e ".[data]"       # Optional: scipy, matplotlib, xgboost
pip install -e ".[jupyter]"    # Optional: Jupyter support

# Frontend
cd mars-ui && npm install && cd ..
```

### Configure

```bash
# .env (project root)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key     # optional
GEMINI_API_KEY=your-gemini-api-key           # optional
PERPLEXITY_API_KEY=your-perplexity-api-key   # optional
MISTRAL_API_KEY=your-mistral-api-key         # optional
```

```bash
# mars-ui/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Run

```bash
# Terminal 1 — Backend
cd backend && python run.py
# → http://localhost:8000  |  Docs: http://localhost:8000/docs

# Terminal 2 — Frontend
cd mars-ui && npm run dev
# → http://localhost:3000
```

### Docker

```bash
docker-compose up --build
# or
docker build -t mars . && docker run -p 3000:3000 -p 8000:8000 -e OPENAI_API_KEY=your-key mars
```

<br/>

---

<br/>

## 📡 API Reference

Full interactive docs at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/tasks` | Create a new task |
| `GET` | `/tasks/{id}` | Get task status |
| `POST` | `/runs` | Start a task run |
| `GET` | `/runs/{id}` | Get run details |
| `POST` | `/sessions` | Create a session |
| `POST` | `/phases/{id}/execute` | Execute a workflow phase |
| `POST` | `/enhance` | Enhance a task description |
| `POST` | `/api/deepresearch/create` | Create a deep research task |
| `POST` | `/api/deepresearch/{id}/stages/{num}/execute` | Execute a research stage |
| `POST` | `/api/arxiv/filter` | Extract and download papers |
| `WS` | `/ws/{task_id}` | Real-time updates |

<details>
<summary><strong>WebSocket Events</strong></summary>

| Event | Description |
|:------|:------------|
| `status` | Task status changes |
| `output` | Agent output streaming |
| `dag_update` | DAG execution progress |
| `approval_request` | HITL approval requests |
| `cost_update` | Token usage and cost tracking |
| `file_created` | New file notifications |
| `error` | Error events |

</details>

<br/>

---

<br/>

## 🔌 External Tools

30+ integrations via CrewAI and LangChain adapters:

**ArXiv** &nbsp;·&nbsp; **Wikipedia** &nbsp;·&nbsp; **DuckDuckGo** &nbsp;·&nbsp; **Perplexity** &nbsp;·&nbsp; **Python REPL** &nbsp;·&nbsp; **Shell** &nbsp;·&nbsp; **File Ops** &nbsp;·&nbsp; **Web Scraping** &nbsp;·&nbsp; **GitHub Search**

<br/>

---

<br/>

## 🧪 Testing

```bash
pytest                       # All tests
pytest -m "not slow"         # Skip slow tests
pytest -m integration        # Integration only
pytest -v                    # Verbose
```

<br/>

---

<br/>

<p align="center">

**Logs** &nbsp;→&nbsp; `~/.cmbagent/logs/backend.log`

**License** &nbsp;→&nbsp; [Apache 2.0](LICENSE)

</p>

<br/>

---

<p align="center">
  <strong>Maintainers</strong><br/>
  <a href="https://github.com/UJ2202">Ujjwal Tiwari</a> (<a href="mailto:22yash.tiwari@gmail.com">22yash.tiwari@gmail.com</a>) &nbsp;&middot;&nbsp;
  <a href="https://github.com/archetana">Chetana Shanbhag</a> (<a href="mailto:Chetana_Shanbhag@infosys.com">Chetana_Shanbhag@infosys.com</a>) &nbsp;&middot;&nbsp;
  <a href="https://github.com/borisbolliet">CMBAgents</a> (<a href="mailto:boris.bolliet@cmbagent.community">boris.bolliet@cmbagent.community</a>)
</p>

<p align="center">
  <strong>Contributors</strong><br/>
  <a href="https://github.com/SACHIN-MOURYA">@SACHIN-MOURYA</a> &nbsp;&middot;&nbsp;
  <a href="https://github.com/khapraravi">@khapraravi</a>
</p>
