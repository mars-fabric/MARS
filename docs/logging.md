# Logging

This document covers all logging patterns, configuration, and conventions used across the three layers of the CMBAgent project: the **cmbagent core library** (Python), the **backend** (FastAPI), and the **mars-ui** (Next.js frontend).

---

## Table of Contents

- [Overview](#overview)
- [Segregated Logging Architecture](#segregated-logging-architecture)
  - [Directory Structure](#directory-structure)
  - [Log File Types](#log-file-types)
  - [What Goes Where](#what-goes-where)
  - [Log Format](#log-format)
  - [Implementation Details](#implementation-details)
  - [Backward Compatibility](#backward-compatibility)
- [Backend Logging](#backend-logging)
  - [Configuration Module](#configuration-module)
  - [Environment Variables](#environment-variables)
  - [Logger Initialization](#logger-initialization)
  - [Structured Logging with structlog](#structured-logging-with-structlog)
  - [Context Binding](#context-binding)
  - [Log Processors](#log-processors)
  - [Output Formats](#output-formats)
  - [Suppressed Loggers](#suppressed-loggers)
  - [Log File Location](#log-file-location)
  - [Startup Logging](#startup-logging)
- [CMBAgent Core Library Logging](#cmbagent-core-library-logging)
  - [Standard Logger Pattern](#standard-logger-pattern)
  - [OrchestratorLogger](#orchestratorlogger)
  - [Debug Utilities](#debug-utilities)
  - [Workflow Callbacks Logger](#workflow-callbacks-logger)
- [Frontend Logging (mars-ui)](#frontend-logging-mars-ui)
  - [Console Methods Used](#console-methods-used)
  - [Debug Configuration](#debug-configuration)
- [Log Levels](#log-levels)
- [AG2 Stdio Capture](#ag2-stdio-capture)
  - [Capture Architecture Overview](#capture-architecture-overview)
  - [AG2 IOStream Override](#ag2-iostream-override)
  - [stdout/stderr Redirection in Task Executor](#stdoutstderr-redirection-in-task-executor)
  - [builtins.print Monkey-Patch](#builtinsprint-monkey-patch)
  - [Isolated Subprocess Capture](#isolated-subprocess-capture)
  - [AG2 Event Hooks](#ag2-event-hooks)
  - [Event Capture Manager](#event-capture-manager)
  - [Console Log File Persistence](#console-log-file-persistence)
  - [CLI Subprocess Capture](#cli-subprocess-capture)
- [Conventions and Best Practices](#conventions-and-best-practices)

---

## Overview

| Layer | Language | Library | Pattern |
|---|---|---|---|
| Backend | Python | `structlog` + stdlib `logging` | `get_logger(__name__)` |
| CMBAgent Core | Python | stdlib `logging` | `logging.getLogger(__name__)` |
| Frontend | TypeScript | Browser `console` API | `console.log/error/warn` |

The backend uses **structured logging** via `structlog` for machine-parseable output with context binding. The core library uses Python's standard `logging` module. The frontend uses the native browser console API.

---

## Segregated Logging Architecture

CMBAgent implements a segregated logging system that separates infrastructure events from agent execution output, providing complete audit trails while maintaining clear separation of concerns.

### Directory Structure

All data is organized under a single configurable root directory (`CMBAGENT_DEFAULT_WORK_DIR`):

```
{CMBAGENT_DEFAULT_WORK_DIR}/
├── logs/
│   └── backend.log                    # Backend system logs (FastAPI, services)
├── database/
│   └── cmbagent.db                    # SQLite database
└── sessions/
    └── {session_id}/
        ├── session.log                 # ALL agent output + events from all runs
        └── runs/
            └── {run_id}/
                ├── run.log             # Infrastructure events only
                └── artifacts/          # Task outputs, files
```

**Default location:** `~/Desktop/cmbdir` (configurable via `CMBAGENT_DEFAULT_WORK_DIR` environment variable)

### Log File Types

CMBAgent maintains three distinct log files:

| Log File | Purpose | Content | Location |
|---|---|---|---|
| **backend.log** | Backend system logging | FastAPI application, services, database operations, WebSocket connections | `{work_dir}/logs/backend.log` |
| **session.log** | Complete session audit trail | ALL agent output, conversations, tool calls, code execution, events from all runs in the session | `{work_dir}/sessions/{session_id}/session.log` |
| **run.log** | Run infrastructure events | Run lifecycle, DAG operations, WebSocket connections, system info (infrastructure only) | `{work_dir}/sessions/{session_id}/runs/{run_id}/run.log` |

### What Goes Where

**backend.log** (System-level logging):
- FastAPI application startup/shutdown
- HTTP request handling
- Database connection and query execution
- Service initialization
- Configuration loading
- Errors and exceptions in backend services

**run.log** (Infrastructure only):
- WebSocket connections/disconnections
- Run lifecycle: started, paused, resumed, completed, failed
- DAG operations: created, updated, node status changes
- System info: work directory, config, resource limits
- Heartbeats (sampled - every 10th)

**session.log** (Everything - complete audit trail):
- **All AG2 stdio output**: Agent conversations, messages, thinking, print() calls
- **Tool calls**: Function calls, arguments, results (FULL content - no truncation)
- **Code execution output**: Code blocks, execution results, errors (FULL content - no truncation)
- **Agent handoffs**: Speaker selection, agent transitions
- **All events**: File creation, approvals, cost updates, errors
- **All run.log events too**: Complete chronological audit trail across all runs

### Log Format

All log files use plain text format with timestamps for simplicity and readability:

```
[2026-02-17 10:30:00.123] [run.started] mode=planning-control agent=engineer model=gpt-4o
[2026-02-17 10:30:01.456] [dag.created] nodes=3 edges=2
[2026-02-17 10:30:05.789] [agent.message] planner: Starting planning phase...
[2026-02-17 10:30:06.012] [tool.call] search_codebase(query="authentication")
[2026-02-17 10:30:08.234] [agent.output] Found 5 authentication implementations
```

**Format structure:** `[timestamp] [event_type] message key1=value1 key2=value2`

**Key characteristics:**
- Plain text (not JSON) for easy reading with standard tools
- ISO 8601 timestamps with millisecond precision
- Event type tags for filtering and parsing
- Key-value pairs for structured data
- **No truncation** - complete content preserved for full audit trail

### Implementation Details

**Core classes** (`backend/loggers/simple_logger.py`):

```python
class SimpleFileLogger:
    """Plain-text logger with async buffering and periodic flushing."""
    def __init__(self, log_path: Path, buffer_size: int = 10):
        self.log_path = Path(log_path)
        self.buffer = []
        self.buffer_size = buffer_size  # Flush after 10 writes
        self.lock = asyncio.Lock()

    async def write(self, event_type: str, message: str, **kwargs):
        """Write a log entry with timestamp and key-value pairs."""
        # Format: [timestamp] [event_type] message key1=val1 key2=val2
        pass

    async def flush(self):
        """Flush buffer to file."""
        pass

class RunLogger(SimpleFileLogger):
    """Logs infrastructure events to run.log"""
    pass

class SessionLogger(SimpleFileLogger):
    """Logs ALL events (including agent output) to session.log"""
    pass
```

**Logger creation** (`backend/loggers/logger_factory.py`):

```python
class LoggerFactory:
    @staticmethod
    def create_loggers(session_id: str, run_id: str, work_dir: str):
        """Create run and session loggers with automatic directory setup."""
        session_dir = Path(work_dir) / "sessions" / session_id
        run_dir = session_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        run_logger = RunLogger(run_dir / "run.log")
        session_logger = SessionLogger(session_dir / "session.log")

        return run_logger, session_logger
```

**Buffering and flushing:**
- Buffer size: 10 lines (reduced from 100 for faster persistence)
- Auto-flush: Every 10 writes to ensure timely file updates
- Explicit flush: Called on run completion/failure
- Thread-safe: Uses `asyncio.Lock` for concurrent access

**AG2 output routing** (`backend/execution/stream_capture.py`):

```python
async def write(self, text: str):
    # Send to WebSocket for real-time UI updates
    await self.send_event(...)

    # Write to session.log (ALL agent output goes here)
    if self.session_logger:
        await self.session_logger.write("agent.output", text.strip())

        # Periodic flush every 10 writes
        self._write_count += 1
        if self._write_count >= self._flush_interval:
            await self.session_logger.flush()
            self._write_count = 0

    # DO NOT write to run.log (agent output is session-level only)
```

**No truncation policy:**
- All truncation limits removed from `stream_capture.py`
- Full agent conversations preserved
- Complete tool call arguments and results
- Full code execution output
- Ensures complete audit trail for debugging and compliance

### Backward Compatibility

For backward compatibility with existing code expecting `console_output.log`:

**Legacy symlink:**
```
{work_dir}/{run_id}/logs/console_output.log  →  ../../sessions/{session_id}/session.log
```

This symlink is automatically created by `LoggerFactory` and points to the session log, preserving the old file path while using the new structure.

**Deprecated API endpoint:**
- `GET /api/runs/{run_id}/console-log` still works but returns a deprecation warning header
- Follows the symlink to read from `session.log`
- Will be removed in a future version

**New API endpoints:**
- `GET /api/runs/{run_id}/logs/run` - Get run-level log (infrastructure only)
- `GET /api/runs/{run_id}/logs/session` - Get session-level log (all agent output)
- `GET /api/runs/{run_id}/logs/stream` - Server-Sent Events (SSE) for live streaming

---

## Backend Logging

### Configuration Module

**File:** `backend/core/logging.py`

This is the central logging configuration for the backend. It sets up `structlog` on top of Python's stdlib `logging` and provides helper functions for context binding.

Key exports:

| Function | Purpose |
|---|---|
| `configure_logging(log_level, json_output, log_file)` | Initialize logging with given settings |
| `get_logger(name)` | Return a `structlog.stdlib.BoundLogger` instance |
| `bind_context(task_id, session_id, run_id)` | Bind tracing context variables |
| `clear_context()` | Clear all bound context variables |
| `LoggingContextManager` | Context manager for automatic bind/cleanup |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CMBAGENT_DEFAULT_WORK_DIR` | `"~/Desktop/cmbdir"` | Root directory for all data: logs, database, sessions, runs |
| `LOG_LEVEL` | `"INFO"` | Minimum log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_JSON` | `"false"` | Set to `"true"` for JSON-formatted output |
| `LOG_FILE` | `"{work_dir}/logs/backend.log"` | File path for backend log output (defaults to work dir if not specified) |
| `CMBAGENT_DATABASE_URL` | `"sqlite:///{work_dir}/database/cmbagent.db"` | Database connection URL (defaults to SQLite in work dir if not specified) |
| `CMBAGENT_DEBUG` | `"false"` | Enables debug-level output in the core library |

**Key configuration:**
- All paths default to subdirectories under `CMBAGENT_DEFAULT_WORK_DIR`
- Database location: `{work_dir}/database/cmbagent.db` (unless custom `CMBAGENT_DATABASE_URL` provided)
- Backend logs: `{work_dir}/logs/backend.log` (unless custom `LOG_FILE` provided)
- Session/run logs: `{work_dir}/sessions/{session_id}/...` (always under work dir)

These are read in `backend/core/app.py` during the FastAPI app lifespan:

```python
_log_config = {
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    "json_output": os.getenv("LOG_JSON", "false").lower() == "true",
    "log_file": os.getenv("LOG_FILE") or _get_default_log_file(),
}

def _get_default_log_file() -> str:
    """Get default log file path in work directory."""
    work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
    work_dir = os.path.expanduser(work_dir)
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / "backend.log")
```

### Logger Initialization

Backend services and routers use the custom `get_logger` function:

```python
from core.logging import get_logger

logger = get_logger(__name__)
```

This returns a `structlog.stdlib.BoundLogger` that supports structured key-value arguments.

**Files using this pattern** (18+ files):
- All routers under `backend/routers/` (sessions, runs, tasks, nodes, enhance, arxiv, branching)
- All services under `backend/services/` (connection_manager, session_manager, workflow_service)
- Execution modules (task_executor, dag_tracker, isolated_executor, stream_capture)
- WebSocket modules (handlers, events)

Some callback modules use the stdlib pattern directly:

```python
import logging
logger = logging.getLogger(__name__)
```

Files: `backend/callbacks/database_callbacks.py`, `backend/callbacks/websocket_callbacks.py`, `backend/execution/cost_collector.py`, `backend/run.py`

### Structured Logging with structlog

Log calls accept keyword arguments that are added as structured fields:

```python
# Structured key-value pairs
logger.info("session_created_via_api", session_id=session_id, mode=request.mode)
logger.debug("workflow_run_created", run_id=self.run_id)
logger.warning("dag_persist_skipped", reason="concurrent_update")
logger.error("task_execution_failed", task_id=task_id, error=str(e))
```

This produces output like:

```
2024-01-15T10:30:45Z [info] session_created_via_api  session_id=abc123  mode=copilot
```

Or in JSON mode:

```json
{"event": "session_created_via_api", "session_id": "abc123", "mode": "copilot", "level": "info", "timestamp": "2024-01-15T10:30:45Z"}
```

### Context Binding

The backend uses `contextvars` to attach tracing IDs to all log entries within a scope. Three context variables are supported:

| Context Variable | Purpose |
|---|---|
| `task_id` | Identifies the current task |
| `session_id` | Identifies the current session |
| `run_id` | Identifies the current workflow run |

**Manual binding:**

```python
from core.logging import bind_context, clear_context

bind_context(task_id="task_123", session_id="sess_456")
logger.info("processing")  # Automatically includes task_id and session_id
clear_context()
```

**Context manager:**

```python
from core.logging import LoggingContextManager

with LoggingContextManager(task_id="task_123"):
    logger.info("processing")  # Includes task_id
# Context automatically cleared
```

### Log Processors

The structlog pipeline processes each log entry through a chain of processors:

1. `merge_contextvars` - Merges async context variables into the log entry
2. `filter_by_level` - Filters out entries below the configured level
3. `add_logger_name` - Adds the logger name (module path)
4. `add_log_level` - Adds the log level string
5. `TimeStamper(fmt="iso")` - Adds ISO 8601 timestamp
6. `StackInfoRenderer()` - Renders stack information if present
7. `format_exc_info` - Formats exception tracebacks
8. `UnicodeDecoder()` - Ensures unicode handling
9. `add_context_processor` (custom) - Injects `task_id`, `session_id`, `run_id`

### Output Formats

**Development (default):** Colorized console output via `structlog.dev.ConsoleRenderer(colors=True)` with plain traceback formatting. Output goes to `sys.stdout`.

**Production (JSON):** Machine-parseable JSON via `structlog.processors.JSONRenderer()`. Enabled by setting `LOG_JSON=true`.

**File output:** Always uses JSON format. Written to the path specified by `LOG_FILE` (default: `~/.cmbagent/logs/backend.log`).

### Suppressed Loggers

Noisy third-party loggers are set to WARNING level to reduce log volume:

```python
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
```

### Log File Location

The default backend log file is created at `{CMBAGENT_DEFAULT_WORK_DIR}/logs/backend.log`. The directory is created automatically on startup if it does not exist.

**Default:** `~/Desktop/cmbdir/logs/backend.log`

All other log files are organized under the same root directory:
- Backend system logs: `{work_dir}/logs/backend.log`
- Database: `{work_dir}/database/cmbagent.db`
- Session logs: `{work_dir}/sessions/{session_id}/session.log`
- Run logs: `{work_dir}/sessions/{session_id}/runs/{run_id}/run.log`

### Startup Logging

On startup (`backend/run.py`), the server logs:

```
Starting CMBAgent Backend Server
Server: http://localhost:8000 | WebSocket: ws://localhost:8000/ws/{task_id} | Docs: http://localhost:8000/docs
Logs will be written to {CMBAGENT_DEFAULT_WORK_DIR}/logs/backend.log
```

After uvicorn initializes, the app lifespan handler re-applies logging configuration (since uvicorn overrides it) and logs:

```
Backend started, logs writing to {CMBAGENT_DEFAULT_WORK_DIR}/logs/backend.log
```

**Note:** The actual path will show the expanded value of `CMBAGENT_DEFAULT_WORK_DIR` (e.g., `/home/user/Desktop/cmbdir/logs/backend.log`).

---

## CMBAgent Core Library Logging

### Standard Logger Pattern

The core Python library (`cmbagent/`) uses Python's stdlib `logging` module:

```python
import logging
logger = logging.getLogger(__name__)
```

This pattern is used across 95+ files in the core library, including:

- `cmbagent/cmbagent.py` - Main orchestration
- `cmbagent/base_agent.py` - Base agent class
- `cmbagent/cli.py` - CLI entry point
- `cmbagent/utils.py` - Utility functions
- All workflow modules under `cmbagent/workflows/`
- All phase modules under `cmbagent/phases/`
- All handoff modules under `cmbagent/handoffs/`

Log calls in the core library use both format-string style and structured key-value style:

```python
# Format-string style
logger.info("One Shot Workflow (%s) | Task: %s", agent, task[:100])
logger.error("get_agent_object_from_name: agent %s not found", name)

# Structured key-value style
logger.debug("path_resolved", path_to_basedir=path_to_basedir)
logger.warning("agent_not_found_in_yaml", agent_name=agent_name)
```

### OrchestratorLogger

**File:** `cmbagent/orchestrator/logger.py`

A custom logger class for orchestration events. Wraps Python's `logging.Logger` with domain-specific methods.

**Format:**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**Output example:**
```
2024-01-15 10:30:45,123 - orchestrator - INFO - Phase started - ID: phase_123, Type: planning
```

**Methods:**

| Method | Purpose |
|---|---|
| `log_phase_start(phase_id, phase_type, task)` | Log phase initialization |
| `log_phase_complete(phase_id, status, duration)` | Log phase completion |
| `log_phase_error(phase_id, error_msg, stack_trace)` | Log phase errors |
| `log_event(message, level, **kwargs)` | Generic event logging |
| `log_chain_start(chain_id, phases)` | Log workflow chain start |
| `log_chain_complete(chain_id, status, duration)` | Log workflow chain completion |
| `log_continuation(session_id, round_count, continuation_count)` | Log workflow continuation |
| `log_swarm_start(session_id, task, config)` | Log swarm orchestration start |
| `log_swarm_complete(session_id, status, rounds, duration)` | Log swarm completion |
| `debug()`, `info()`, `warning()`, `error()` | Convenience level methods |

**Handler setup:**
- Console handler via `StreamHandler` to stdout
- Optional file handler via `FileHandler`
- Both use the same `Formatter`

### Debug Utilities

**File:** `cmbagent/handoffs/debug.py`

A conditional debug printing module controlled by the `cmbagent_debug` flag (default: `False`, set via `CMBAGENT_DEBUG` environment variable).

```python
from cmbagent.handoffs.debug import debug_print, debug_section, is_debug_enabled

debug_section("Handoff Resolution")    # Only logs if debug enabled
debug_print("Processing agent: foo")   # Only logs if debug enabled
```

Functions:

| Function | Purpose |
|---|---|
| `is_debug_enabled()` | Returns whether debug mode is active |
| `debug_print(message, indent)` | Conditional debug log with indentation levels |
| `debug_section(title)` | Conditional section header log |

Used in 11+ handoff modules for conditional debug output.

### Workflow Callbacks Logger

**File:** `cmbagent/callbacks.py`

A pre-configured set of callbacks that log workflow lifecycle events:

```python
_logger = logging.getLogger(__name__ + ".print_callbacks")

print_callbacks = WorkflowCallbacks(
    on_planning_start=lambda task, config: _logger.info("planning_started task=%s", task[:100]),
    on_planning_complete=lambda plan: _logger.info("planning_complete num_steps=%s", plan.num_steps),
    on_step_start=lambda step: _logger.info("step_started step_number=%s goal=%s", step.step_number, step.goal),
    on_step_complete=lambda step: _logger.info("step_completed step_number=%s", step.step_number),
    on_step_failed=lambda step: _logger.error("step_failed step_number=%s error=%s", step.step_number, step.error),
    on_workflow_start=lambda task, config: _logger.info("workflow_started"),
    on_workflow_complete=lambda ctx, time: _logger.info("workflow_complete total_time=%.2f", time),
    on_workflow_failed=lambda err, step: _logger.error("workflow_failed step=%s error=%s", step, err),
)
```

---

## Frontend Logging (mars-ui)

### Console Methods Used

The Next.js frontend uses the native browser `console` API. There is no logging library.

**`console.log()`** - General informational output:
```typescript
console.log('[WebSocket] Approval requested event received:', data);
console.log(`[WebSocket] Connecting to ${wsUrl}...`);
```

**`console.error()`** - Error reporting:
```typescript
console.error('Error sending ping:', error);
console.error('Error testing credentials:', error);
```

**`console.warn()`** - Warnings:
```typescript
console.warn('[WebSocket] Cannot send message, not connected');
```

50+ `console.log` calls exist across the frontend codebase, primarily in:

| File | Purpose |
|---|---|
| `contexts/WebSocketContext.tsx` | WebSocket connection lifecycle, events, errors |
| `hooks/useResilientWebSocket.ts` | Connection/reconnection logging |
| `components/CredentialsModal.tsx` | Credential testing errors |

Most frontend log messages use a `[WebSocket]` prefix for easy filtering in browser DevTools.

### Debug Configuration

**File:** `mars-ui/lib/config.ts`

```typescript
debug: process.env.NEXT_PUBLIC_DEBUG === 'true',
```

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_DEBUG` | `"false"` | Enables debug-level frontend logging |

---

## Log Levels

All four standard Python log levels are used across the project:

| Level | Usage |
|---|---|
| `DEBUG` | Detailed diagnostic information: resolved paths, DAG state checks, WebSocket frame details, config dumps |
| `INFO` | Normal operational events: service startup, session creation, workflow execution, phase transitions |
| `WARNING` | Unexpected but recoverable situations: missing session state, failed WebSocket sends, DAG persist skips, noisy library suppression |
| `ERROR` | Failures requiring attention: database errors, task execution failures, WebSocket handler errors, cost collection failures |

The default level is `INFO`. Set `LOG_LEVEL=DEBUG` for verbose output during development.

---

## AG2 Stdio Capture

AG2 (AutoGen 2) agents produce output through multiple channels: their own `IOStream` interface, direct `print()` calls, and structured event objects. The backend uses a layered interception system to capture all of this output and route it to:
1. **WebSocket** (for real-time UI updates)
2. **session.log** (for complete audit trail across all runs)
3. **run.log** (for infrastructure events only)

### Capture Architecture Overview

There are two execution modes, each with its own capture stack:

**In-process execution** (`backend/execution/task_executor.py`):

```
AG2 Agent
  ├── IOStream.print() / IOStream.send()  →  AG2IOStreamCapture  →  WebSocket + session.log
  ├── builtins.print()                     →  monkey-patched print →  WebSocket + session.log
  └── sys.stdout / sys.stderr              →  StreamWrapper        →  StreamCapture  →  WebSocket + session.log
```

**Isolated subprocess execution** (`backend/execution/isolated_executor.py`):

```
AG2 Agent (in spawned Process)
  ├── IOStream.print() / IOStream.send()  →  QueueIOStream    →  multiprocessing.Queue
  ├── builtins.print()                     →  captured_print   →  multiprocessing.Queue
  └── sys.stdout / sys.stderr              →  QueueWriter      →  multiprocessing.Queue
                                                                         │
                                                     _monitor_subprocess ←┘  →  output_callback  →  WebSocket + session.log
```

Both paths persist output to `{work_dir}/sessions/{session_id}/session.log` for complete audit trail.

Summary of all capture mechanisms:

| Mechanism | File | Method | Destination |
|---|---|---|---|
| AG2 IOStream override | `backend/execution/stream_capture.py` | `IOStream.set_global_default()` | WebSocket + session.log |
| stdout/stderr redirect | `backend/execution/task_executor.py` | `StreamWrapper` class | WebSocket + session.log |
| `builtins.print` hook | `backend/execution/task_executor.py` | Monkey-patch | WebSocket + session.log |
| AG2 IOStream (subprocess) | `backend/execution/isolated_executor.py` | `QueueIOStream` class | `multiprocessing.Queue` → session.log |
| `builtins.print` (subprocess) | `backend/execution/isolated_executor.py` | `captured_print` function | `multiprocessing.Queue` → session.log |
| stdout/stderr (subprocess) | `backend/execution/isolated_executor.py` | `QueueWriter` class | `multiprocessing.Queue` → session.log |
| AG2 event hooks | `cmbagent/execution/ag2_hooks.py` | `functools.wraps` patches | `EventCaptureManager` → session.log |
| Event capture context | `cmbagent/execution/event_capture.py` | `contextvars.ContextVar` | Database + WebSocket + session.log |
| CLI subprocess stdio | `cmbagent/cli.py` | `subprocess.PIPE` | Captured via `communicate()` |
| Session log persistence | `backend/execution/stream_capture.py` | SessionLogger | `{work_dir}/sessions/{session_id}/session.log` |
| Run log persistence | `backend/execution/stream_capture.py` | RunLogger | `{work_dir}/sessions/{session_id}/runs/{run_id}/run.log` |

### AG2 IOStream Override

**File:** `backend/execution/stream_capture.py`

The `AG2IOStreamCapture` class implements AG2's `IOStream` interface and is set as the global default so that all AG2 agent output flows through it.

```python
from autogen.io.base import IOStream

ag2_iostream = AG2IOStreamCapture(websocket, task_id, send_ws_event, loop,
                                   run_logger=run_logger,
                                   session_logger=session_logger,
                                   session_id=session_id)
IOStream.set_global_default(ag2_iostream)
```

Key methods:

| Method | Purpose |
|---|---|
| `print(*args, **kwargs)` | Captures text output from agents, forwards to WebSocket and session.log via `_send_output()` |
| `send(message)` | Intercepts AG2 `BaseEvent` objects, extracts structured data |
| `_extract_event_data(event)` | Parses event type, sender, recipient, content (FULL - no truncation), function calls, tool calls, and tool responses |
| `_send_output(text)` | Async WebSocket sender using `asyncio.run_coroutine_threadsafe()` |
| `_send_structured_event(event_data)` | Converts AG2 events to standardized WebSocket events, logs to session.log (FULL content - no truncation) |
| `input(prompt)` | Handles input requests from agents |

**Important changes:**
- **No truncation**: All content is preserved in full (previously truncated to 5000, 2000, 500, or 200 chars)
- **Dual logging**: All events written to both session.log (complete audit trail) and optionally run.log (infrastructure only)
- **Periodic flushing**: Automatic flush every 10 writes to ensure timely persistence

### stdout/stderr Redirection in Task Executor

**File:** `backend/execution/task_executor.py`

Before executing a task, the task executor saves the original streams and installs `StreamWrapper` objects:

```python
original_stdout = sys.stdout
original_stderr = sys.stderr

sys.stdout = StreamWrapper(original_stdout, stream_capture, loop, suppress=suppress_stdout)
sys.stderr = StreamWrapper(original_stderr, stream_capture, loop, suppress=False)
```

The `StreamWrapper` class:
- Conditionally writes to the original stream (suppressed for HITL/copilot modes to keep the terminal clean)
- Forwards all text to `stream_capture.write()` asynchronously via `asyncio.run_coroutine_threadsafe()`
- Implements `write()`, `flush()`, `fileno()`, `isatty()` so it can be used as a drop-in stream replacement

The underlying `StreamCapture` class (`backend/execution/stream_capture.py`) receives the forwarded text and:
1. Sends it to the frontend via WebSocket
2. Writes it to `{work_dir}/sessions/{session_id}/session.log` via SessionLogger
3. Maintains a `StringIO` buffer

**Key changes:**
- Replaced direct file writes to `console_output.log` with SessionLogger calls
- Periodic flushing every 10 writes for timely persistence
- No truncation - all output preserved in full

### builtins.print Monkey-Patch

**File:** `backend/execution/task_executor.py`

In addition to stream redirection, `builtins.print` is replaced to catch any code that calls `print()` directly (bypassing `sys.stdout`):

```python
original_print = builtins.print

def custom_print(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    asyncio.run_coroutine_threadsafe(stream_capture.write(text), loop)
    if not suppress_stdout:
        original_print(*args, **kwargs)

builtins.print = custom_print
```

This is restored after task execution completes.

### Isolated Subprocess Capture

**File:** `backend/execution/isolated_executor.py`

When tasks run in isolated subprocesses (via `multiprocessing.Process` with `'spawn'` start method), a different capture strategy is needed since WebSocket connections cannot be shared across process boundaries.

**QueueWriter** replaces `sys.stdout` and `sys.stderr` in the subprocess:

```python
class QueueWriter:
    def write(self, text):
        # Routes stdout as "output", stderr as "error"
        output_queue.put((self.stream_type, {"message": text}))
```

**QueueIOStream** replaces AG2's `IOStream` in the subprocess:

```python
class QueueIOStream(IOStream):
    def print(self, *args, **kwargs):
        message = " ".join(str(arg) for arg in args)
        send_output("output", {"message": message, "source": "ag2"})

    def send(self, message):
        # Captures AG2 structured events
        send_output("ag2_event", {...})
```

**captured_print** replaces `builtins.print`:

```python
def captured_print(*args, **kwargs):
    output_queue.put(("print", {"message": " ".join(str(a) for a in args)}))
    original_print(*args, **kwargs)
```

The parent process runs `_monitor_subprocess()` which drains the `multiprocessing.Queue` in a non-blocking loop, forwarding events through the `output_callback` to WebSocket.

### AG2 Event Hooks

**File:** `cmbagent/execution/ag2_hooks.py`

This module monkey-patches AG2's core classes to capture structured events about agent interactions. It uses `functools.wraps` to preserve original method metadata.

**Patched classes and methods:**

| Class | Method | What is captured |
|---|---|---|
| `ConversableAgent` | `generate_reply()` | Agent calls and responses |
| `ConversableAgent` | `send()` | Agent-to-agent messages |
| `GroupChat` | `select_speaker()` | Agent handoffs / speaker selection |
| `LocalCommandLineCodeExecutor` | `execute_code_blocks()` | Code execution with timing, exit code, and output |

Installation is idempotent via a global `_hooks_installed` flag:

```python
from cmbagent.execution import install_ag2_hooks

install_ag2_hooks()  # Safe to call multiple times
```

Events captured by these hooks are sent to the `EventCaptureManager`.

### Event Capture Manager

**File:** `cmbagent/execution/event_capture.py`

The `EventCaptureManager` is a thread-safe event collection system that aggregates all captured AG2 events and forwards them to the database, WebSocket, and session.log.

**Event types captured:** `agent_call`, `tool_call`, `code_exec`, `file_gen`, `handoff`, `message`, `error`

**Key features:**
- Uses `contextvars.ContextVar` for async-safe context isolation
- Tracks parent-child event relationships via an `event_stack`
- Maintains execution order tracking
- **No truncation** - full code blocks and outputs preserved (previously truncated to 1000/5000 chars)
- Emits events to WebSocket via async callbacks
- Persists to session.log for complete audit trail

**Context management:**

```python
from cmbagent.execution import get_event_captor, set_event_captor, EventCaptureManager

captor = EventCaptureManager(...)
set_event_captor(captor)

# Later, from any async context:
captor = get_event_captor()
captor.capture_event(...)
```

### Console Log File Persistence

Both execution modes persist all captured console output to segregated log files:

**Session log:** `{work_dir}/sessions/{session_id}/session.log`
- Contains ALL agent output, events, and interactions
- Spans multiple runs within the same session
- Complete audit trail with no truncation
- Written by `SessionLogger` in `backend/execution/stream_capture.py`

**Run log:** `{work_dir}/sessions/{session_id}/runs/{run_id}/run.log`
- Contains infrastructure events only (connections, lifecycle, DAG operations)
- Specific to a single run
- Written by `RunLogger` in `backend/execution/stream_capture.py`

**Legacy compatibility:** For backward compatibility, a symlink is created at:
```
{work_dir}/{run_id}/logs/console_output.log → ../../sessions/{session_id}/session.log
```

**Implementation:**
- In-process: Written by `StreamCapture.write()` via SessionLogger/RunLogger
- Subprocess: Written by the log file handler in `backend/execution/isolated_executor.py`
- Both use async I/O with buffering (buffer size: 10 lines)
- Periodic flush every 10 writes ensures timely persistence
- Explicit flush on run completion/failure

These files contain a complete record of all stdout/stderr output from the task execution, useful for post-mortem debugging and compliance auditing.

### CLI Subprocess Capture

**File:** `cmbagent/cli.py`

When the CLI launches the backend and frontend as subprocesses, their stdio is captured via `subprocess.PIPE`:

```python
backend_process = subprocess.Popen(
    [sys.executable, "run.py"],
    cwd=backend_path,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

frontend_process = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd=frontend_path,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
```

Output is retrieved via `communicate()` and process status is monitored in a polling loop.

---

## Conventions and Best Practices

1. **Always use `get_logger(__name__)` in backend code** to get a structured logger with context support.

2. **Always use `logging.getLogger(__name__)` in core library code** for consistency with the existing pattern.

3. **Use structured key-value arguments** for log data rather than string interpolation:
   ```python
   # Preferred
   logger.info("session_created", session_id=sid, mode=mode)

   # Avoid
   logger.info(f"Session {sid} created in mode {mode}")
   ```

4. **Use context binding** when entering a task/session/run scope so all subsequent logs include tracing IDs:
   ```python
   with LoggingContextManager(task_id=task_id, session_id=session_id):
       # All logs here automatically include task_id and session_id
       logger.info("processing_started")
   ```

5. **Use event-style log messages** (lowercase, underscored) as the first argument rather than full sentences:
   ```python
   logger.info("workflow_run_created", run_id=run_id)  # Preferred
   logger.info("A new workflow run was created")         # Avoid
   ```

6. **Prefix frontend console messages** with `[Component]` for easy filtering in DevTools:
   ```typescript
   console.log('[WebSocket] Connected');
   ```

7. **Do not log sensitive data** such as API keys, credentials, or full request/response bodies from LLM providers.

8. **Suppress noisy third-party loggers** by setting them to WARNING level in the logging configuration rather than in individual modules.

9. **Understand the segregated logging architecture**:
   - `backend.log` = Backend system logs (FastAPI, services, database)
   - `session.log` = Complete audit trail of ALL agent output and events across runs
   - `run.log` = Infrastructure events for a specific run
   - Agent conversations, tool calls, code execution → always goes to `session.log`
   - WebSocket connections, DAG operations → goes to both `run.log` and `session.log`

10. **Never truncate agent output** - the segregated logging system preserves complete content for full audit trails and debugging.

11. **Use SessionLogger for all agent output, RunLogger for infrastructure events** when working with the execution system.

12. **Configure CMBAGENT_DEFAULT_WORK_DIR** in production to set a persistent location for all logs, database, and session data.
