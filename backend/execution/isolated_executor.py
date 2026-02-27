"""
Isolated Task Executor (Stage 6)

Executes CMBAgent tasks in separate subprocesses to prevent global state pollution.
Each task gets its own Python interpreter with isolated:
- builtins.print
- sys.stdout/stderr
- IOStream settings
- All global state

Output is routed via multiprocessing.Queue back to the main process for WebSocket delivery.
"""

import asyncio
import logging
import multiprocessing
import os
import queue
import sys
import time
import traceback
from datetime import datetime, timezone
from multiprocessing import Process, Queue
from typing import Any, Callable, Dict, Optional, Awaitable

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class IsolatedTaskExecutor:
    """
    Execute tasks in isolated subprocesses.

    Benefits:
    - True process isolation (no global pollution)
    - Works with any library that modifies globals
    - Proper resource cleanup on task completion/failure
    - Task cancellation via process termination
    """

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._active_processes: Dict[str, Process] = {}
        self._process_lock = asyncio.Lock()

        # Set multiprocessing start method (spawn for isolation)
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # Already set

        logger.info("IsolatedTaskExecutor initialized (max_workers=%d)", max_workers)

    async def execute(
        self,
        task_id: str,
        task: str,
        config: Dict[str, Any],
        output_callback: Callable[[str, Dict[str, Any]], Awaitable[None]],
        work_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a task in an isolated subprocess.

        Args:
            task_id: Unique task identifier
            task: Task description
            config: Task configuration
            output_callback: Async callback for output events (event_type, data)
            work_dir: Working directory for the task

        Returns:
            Task result dictionary

        Raises:
            RuntimeError: If max workers exceeded or execution fails
        """
        async with self._process_lock:
            if len(self._active_processes) >= self.max_workers:
                raise RuntimeError(f"Max workers ({self.max_workers}) exceeded")

        # Create queues for IPC
        output_queue = Queue()
        result_queue = Queue()

        # Determine work directory
        if not work_dir:
            work_dir = os.path.expanduser(config.get("workDir", settings.default_work_dir))

        # Get session_id from config (default to "default_session" if not provided)
        session_id = config.get("session_id", "default_session")

        # Create task directory nested under session
        # Structure: {work_dir}/sessions/{session_id}/tasks/{task_id}
        task_work_dir = os.path.join(work_dir, "sessions", session_id, "tasks", task_id)
        os.makedirs(task_work_dir, exist_ok=True)

        # Create standard subdirectories that agents expect
        # These match the directories created in cmbagent.py
        os.makedirs(os.path.join(task_work_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(task_work_dir, "codebase"), exist_ok=True)
        os.makedirs(os.path.join(task_work_dir, "chats"), exist_ok=True)
        os.makedirs(os.path.join(task_work_dir, "planning"), exist_ok=True)
        os.makedirs(os.path.join(task_work_dir, "control"), exist_ok=True)

        # Start subprocess
        process = Process(
            target=_run_task_in_subprocess,
            args=(task_id, task, config, output_queue, result_queue, task_work_dir),
            daemon=True
        )
        process.start()

        async with self._process_lock:
            self._active_processes[task_id] = process

        logger.info("Started subprocess for task %s (pid=%d)", task_id, process.pid)

        try:
            # Monitor output queue and forward to callback
            result = await self._monitor_subprocess(
                task_id, process, output_queue, result_queue, output_callback
            )
            return result

        finally:
            async with self._process_lock:
                self._active_processes.pop(task_id, None)

            # Ensure process is terminated
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2.0)

            logger.info("Subprocess for task %s cleaned up", task_id)

    async def _monitor_subprocess(
        self,
        task_id: str,
        process: Process,
        output_queue: Queue,
        result_queue: Queue,
        output_callback: Callable
    ) -> Dict[str, Any]:
        """Monitor subprocess and handle output routing."""

        while True:
            # Drain all available output (non-blocking)
            try:
                while True:
                    try:
                        event_type, data = output_queue.get_nowait()
                        await output_callback(event_type, data)
                    except queue.Empty:
                        break
            except Exception as e:
                logger.warning("Error processing output for task %s: %s", task_id, e)

            # Check if process finished
            if not process.is_alive():
                # Drain remaining output
                try:
                    while True:
                        event_type, data = output_queue.get_nowait()
                        await output_callback(event_type, data)
                except queue.Empty:
                    pass

                # Get result
                try:
                    result = result_queue.get(timeout=5.0)
                    if isinstance(result, Exception):
                        raise result
                    return result
                except queue.Empty:
                    exit_code = process.exitcode
                    raise RuntimeError(
                        f"Task process terminated unexpectedly (exit code: {exit_code})"
                    )

            # Yield control briefly
            await asyncio.sleep(0.05)

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Returns:
            True if cancelled, False if not found
        """
        async with self._process_lock:
            process = self._active_processes.get(task_id)
            if not process:
                return False

        logger.info("Cancelling task %s", task_id)

        # Try graceful termination first
        process.terminate()
        process.join(timeout=5.0)

        if process.is_alive():
            process.kill()
            process.join(timeout=2.0)

        return True

    async def get_active_tasks(self) -> list:
        """Get list of active task IDs."""
        async with self._process_lock:
            return list(self._active_processes.keys())


# ---------------------------------------------------------------------------
# Subprocess entry point (runs in isolated process)
# ---------------------------------------------------------------------------

def _run_task_in_subprocess(
    task_id: str,
    task: str,
    config: Dict[str, Any],
    output_queue: Queue,
    result_queue: Queue,
    work_dir: str
):
    """
    Run task in isolated subprocess.

    This function runs in a SEPARATE PROCESS with completely isolated globals.
    It's safe to modify builtins.print, sys.stdout, etc. here.
    """
    import builtins

    # Store original streams
    original_print = builtins.print
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    def send_output(event_type: str, data: Dict[str, Any]):
        """Thread-safe output sending via queue."""
        try:
            output_queue.put((event_type, data), timeout=1.0)
        except queue.Full:
            pass  # Drop if queue full

    # Open console log file for persistence
    _console_log_file = None
    try:
        log_dir = os.path.join(work_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        _console_log_file = open(
            os.path.join(log_dir, "console_output.log"), "a", encoding="utf-8"
        )
    except Exception:
        pass

    _original_send_output = send_output

    def send_output(event_type: str, data: Dict[str, Any]):
        """Thread-safe output sending via queue + file persistence."""
        _original_send_output(event_type, data)
        if _console_log_file and event_type in ("output", "error", "agent_event", "agent_message"):
            msg = data.get("message") or data.get("content") or ""
            if msg:
                try:
                    _console_log_file.write(msg + "\n")
                    _console_log_file.flush()
                except Exception:
                    pass

    def send_dag_event(dag_event_type: str, data: Dict[str, Any]):
        """Send DAG-related events (Stage 7)."""
        send_output(f"dag_{dag_event_type}", data)

    def send_cost_event(model: str, input_tokens: int, output_tokens: int, cost: float):
        """Send cost tracking event (Stage 7)."""
        send_output("cost_update", {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def send_phase_event(phase: str, step: Optional[int] = None):
        """Send phase change event (Stage 7)."""
        send_output("phase_change", {
            "phase": phase,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def captured_print(*args, **kwargs):
        """Captured print that sends to queue."""
        message = " ".join(str(arg) for arg in args)
        send_output("output", {"message": message, "source": "print"})
        # Also print to actual stdout for debugging
        original_print(*args, **kwargs)

    class QueueWriter:
        """Stream writer that sends to queue."""
        def __init__(self, stream_name: str, original_stream=None):
            self.stream_name = stream_name
            self.buffer = ""
            self._original_stream = original_stream

        def write(self, text):
            if text:
                self.buffer += text
                # Flush on newline
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line.strip():
                        send_output(
                            "output" if self.stream_name == "stdout" else "error",
                            {"message": line, "source": "stream"}
                        )
            return len(text) if text else 0

        def flush(self):
            if self.buffer.strip():
                send_output(
                    "output" if self.stream_name == "stdout" else "error",
                    {"message": self.buffer, "source": "stream"}
                )
                self.buffer = ""

        def fileno(self):
            if self._original_stream is not None:
                return self._original_stream.fileno()
            raise AttributeError("QueueWriter has no fileno")

        def isatty(self):
            return False

    try:
        # Override globals (safe - isolated process!)
        builtins.print = captured_print
        sys.stdout = QueueWriter("stdout", original_stdout)
        sys.stderr = QueueWriter("stderr", original_stderr)

        # Set up AG2 IOStream if available
        try:
            from autogen.io.base import IOStream

            class QueueIOStream(IOStream):
                def print(self, *args, **kwargs):
                    message = " ".join(str(arg) for arg in args)
                    send_output("output", {"message": message, "source": "ag2"})

                def send(self, message):
                    """Capture AG2 structured events."""
                    try:
                        event_type = type(message).__name__
                        sender = getattr(getattr(message, 'content', message), 'sender', None)
                        content_str = str(message)[:500]
                        send_output("agent_event", {
                            "ag2_event_type": event_type,
                            "sender": sender,
                            "content": content_str,
                            "source": "ag2"
                        })
                    except Exception:
                        pass
                    # Also call default print
                    try:
                        message.print(original_print)
                    except Exception:
                        pass

            IOStream.set_global_default(QueueIOStream())
        except ImportError:
            pass

        # Set environment
        os.environ["CMBAGENT_DEBUG"] = "false"
        os.environ["CMBAGENT_DISABLE_DISPLAY"] = "true"
        os.chdir(work_dir)

        send_output("status", {"message": "Starting task execution..."})

        # Execute CMBAgent task
        result = _execute_cmbagent_task(
            task_id, task, config, work_dir,
            send_output, send_dag_event, send_cost_event, send_phase_event
        )

        # Send success
        result_queue.put(result)

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()

        send_output("error", {
            "message": error_msg,
            "traceback": tb,
            "error_type": type(e).__name__
        })

        result_queue.put(RuntimeError(f"Task failed: {error_msg}"))

    finally:
        # Flush remaining buffered output
        if isinstance(sys.stdout, QueueWriter):
            sys.stdout.flush()
        if isinstance(sys.stderr, QueueWriter):
            sys.stderr.flush()

        # Close console log file
        if _console_log_file:
            try:
                _console_log_file.close()
            except Exception:
                pass

        # Restore (not strictly necessary as process is ending)
        builtins.print = original_print
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def _execute_cmbagent_task(
    task_id: str,
    task: str,
    config: Dict[str, Any],
    work_dir: str,
    send_output: Callable,
    send_dag_event: Callable,
    send_cost_event: Callable,
    send_phase_event: Callable
) -> Dict[str, Any]:
    """
    Execute the actual CMBAgent task.

    Separated out for clarity and to allow mode-specific handling.
    Includes DAG creation and phase tracking (Stage 7).
    """
    import cmbagent
    from cmbagent.utils import get_api_keys_from_env

    api_keys = get_api_keys_from_env()
    mode = config.get("mode", "one-shot")

    send_output("output", {"message": f"Executing in {mode.replace('-', ' ').title()} mode..."})

    # Extract common config
    engineer_model = config.get("model", "gpt-4o")
    max_rounds = config.get("maxRounds", 25)
    max_attempts = config.get("maxAttempts", 6)
    default_formatter_model = config.get("defaultFormatterModel", "o3-mini-2025-01-31")
    default_llm_model = config.get("defaultModel", "gpt-4.1-2025-04-14")

    # Create DAG structure for visualization (Stage 7)
    dag = _create_dag_for_mode(mode, task, config)
    send_output("dag_created", dag)

    def update_dag_node(node_id: str, status: str, **kwargs):
        """Update a DAG node status."""
        send_output("dag_node_update", {
            "node_id": node_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs
        })

    # Mark start node
    update_dag_node("start", "completed")

    start_time = time.time()

    # Create callbacks for tracking
    try:
        from cmbagent.callbacks import (
            create_print_callbacks, WorkflowCallbacks, merge_callbacks
        )

        def on_phase_change(phase: str, step_number: int = None):
            send_phase_event(phase, step_number)

        def on_planning_complete(plan_info):
            update_dag_node("planning", "completed")
            if plan_info and hasattr(plan_info, 'steps') and plan_info.steps:
                # Dynamically add step nodes to DAG
                for i, step in enumerate(plan_info.steps):
                    step_label = getattr(step, 'description', f"Step {i+1}")[:50]
                    send_output("dag_node_add", {
                        "node_id": f"step_{i+1}",
                        "label": step_label,
                        "type": "step",
                        "status": "pending",
                        "after": "planning" if i == 0 else f"step_{i}",
                        "before": "end"
                    })
            send_phase_event("execution", None)

        def on_step_start(step_info):
            step_num = getattr(step_info, 'step_number', None)
            if step_num:
                update_dag_node(f"step_{step_num}", "running")
                send_phase_event("execution", step_num)

        def on_step_complete(step_info):
            step_num = getattr(step_info, 'step_number', None)
            if step_num:
                update_dag_node(f"step_{step_num}", "completed")

        def on_step_failed(step_info):
            step_num = getattr(step_info, 'step_number', None)
            if step_num:
                error = getattr(step_info, 'error', 'Unknown error')
                update_dag_node(f"step_{step_num}", "failed", error=str(error))

        def on_agent_message(agent, role, content, metadata):
            send_output("agent_message", {
                "agent": agent,
                "role": role,
                "content": content[:2000] if content else "",
                "source": "callback"
            })

        tracking_callbacks = WorkflowCallbacks(
            on_phase_change=on_phase_change,
            on_planning_complete=on_planning_complete,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
            on_step_failed=on_step_failed,
            on_agent_message=on_agent_message,
        )
        print_callbacks = create_print_callbacks()
        workflow_callbacks = merge_callbacks(print_callbacks, tracking_callbacks)
    except ImportError:
        workflow_callbacks = None

    # Execute based on mode
    if mode == "one-shot":
        agent = config.get("agent", "engineer")
        update_dag_node("execute", "running")
        send_phase_event("execution", None)

        results = cmbagent.one_shot(
            task=task,
            max_rounds=max_rounds,
            max_n_attempts=max_attempts,
            engineer_model=engineer_model,
            agent=agent,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False,
            default_formatter_model=default_formatter_model,
            default_llm_model=default_llm_model
        )
        update_dag_node("execute", "completed")

    elif mode == "planning-control":
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        researcher_model = config.get("researcherModel", "gpt-4.1-2025-04-14")
        max_plan_steps = config.get("maxPlanSteps", 10)
        n_plan_reviews = config.get("nPlanReviews", 1)
        plan_instructions = config.get("planInstructions", "")

        update_dag_node("planning", "running")
        send_phase_event("planning", None)

        # Set up approval configuration for HITL
        approval_config = None
        approval_mode = config.get("approvalMode", "none")
        if approval_mode != "none":
            from cmbagent.database.approval_types import ApprovalMode, ApprovalConfig
            mode_map = {
                "after_planning": ApprovalMode.AFTER_PLANNING,
                "before_each_step": ApprovalMode.BEFORE_EACH_STEP,
                "on_error": ApprovalMode.ON_ERROR,
                "manual": ApprovalMode.MANUAL,
            }
            if approval_mode in mode_map:
                approval_config = ApprovalConfig(mode=mode_map[approval_mode])

        results = cmbagent.planning_and_control_context_carryover(
            task=task,
            max_rounds_control=max_rounds,
            max_n_attempts=max_attempts,
            max_plan_steps=max_plan_steps,
            n_plan_reviews=n_plan_reviews,
            engineer_model=engineer_model,
            researcher_model=researcher_model,
            planner_model=planner_model,
            plan_reviewer_model=plan_reviewer_model,
            plan_instructions=plan_instructions if plan_instructions.strip() else None,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False,
            default_formatter_model=default_formatter_model,
            default_llm_model=default_llm_model,
            callbacks=workflow_callbacks,
            approval_config=approval_config
        )

    elif mode == "idea-generation":
        idea_maker_model = config.get("ideaMakerModel", "gpt-4.1-2025-04-14")
        idea_hater_model = config.get("ideaHaterModel", "o3-mini-2025-01-31")
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        max_plan_steps = config.get("maxPlanSteps", 10)
        n_plan_reviews = config.get("nPlanReviews", 1)
        plan_instructions = config.get("planInstructions", "")

        update_dag_node("planning", "running")
        send_phase_event("planning", None)

        results = cmbagent.planning_and_control_context_carryover(
            task=task,
            max_rounds_control=max_rounds,
            max_n_attempts=max_attempts,
            max_plan_steps=max_plan_steps,
            n_plan_reviews=n_plan_reviews,
            idea_maker_model=idea_maker_model,
            idea_hater_model=idea_hater_model,
            planner_model=planner_model,
            plan_reviewer_model=plan_reviewer_model,
            plan_instructions=plan_instructions if plan_instructions.strip() else None,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False,
            default_formatter_model=default_formatter_model,
            default_llm_model=default_llm_model,
            callbacks=workflow_callbacks
        )

    elif mode == "ocr":
        pdf_path = task.strip()
        if pdf_path.startswith("~"):
            pdf_path = os.path.expanduser(pdf_path)

        save_markdown = config.get("saveMarkdown", True)
        save_json = config.get("saveJson", True)
        save_text = config.get("saveText", False)
        max_workers = config.get("maxWorkers", 4)
        ocr_output_dir = config.get("ocrOutputDir", None)
        output_dir = ocr_output_dir if ocr_output_dir and ocr_output_dir.strip() else None

        update_dag_node("execute", "running")
        send_phase_event("execution", None)

        if os.path.isfile(pdf_path):
            results = cmbagent.process_single_pdf(
                pdf_path=pdf_path,
                save_markdown=save_markdown,
                save_json=save_json,
                save_text=save_text,
                output_dir=output_dir,
                work_dir=work_dir
            )
        elif os.path.isdir(pdf_path):
            results = cmbagent.process_folder(
                folder_path=pdf_path,
                save_markdown=save_markdown,
                save_json=save_json,
                save_text=save_text,
                output_dir=output_dir,
                max_workers=max_workers,
                work_dir=work_dir
            )
        else:
            raise ValueError(f"Path not found: {pdf_path}")

        update_dag_node("execute", "completed")

    elif mode == "arxiv":
        update_dag_node("execute", "running")
        send_phase_event("execution", None)

        results = cmbagent.arxiv_filter(
            input_text=task,
            work_dir=work_dir
        )
        update_dag_node("execute", "completed")

    elif mode == "enhance-input":
        max_workers = config.get("maxWorkers", 4)
        update_dag_node("execute", "running")
        send_phase_event("execution", None)

        results = cmbagent.preprocess_task(
            text=task,
            work_dir=work_dir,
            max_workers=max_workers,
            clear_work_dir=False
        )
        update_dag_node("execute", "completed")

    else:
        # Fallback to one-shot for unknown modes
        send_output("output", {"message": f"Unknown mode '{mode}', using one-shot"})
        update_dag_node("execute", "running")

        results = cmbagent.one_shot(
            task=task,
            max_rounds=max_rounds,
            max_n_attempts=max_attempts,
            engineer_model=engineer_model,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False
        )
        update_dag_node("execute", "completed")

    execution_time = time.time() - start_time

    # Mark end node
    update_dag_node("end", "completed")
    send_phase_event("completed", None)

    send_output("output", {"message": f"Task completed in {execution_time:.2f}s"})

    return {
        "status": "completed",
        "execution_time": execution_time,
        "work_dir": work_dir,
        "mode": mode,
        "chat_history": getattr(results, 'chat_history', []) if hasattr(results, 'chat_history') else [],
        "final_context": getattr(results, 'final_context', {}) if hasattr(results, 'final_context') else {},
        "session_id": results.get('session_id') if isinstance(results, dict) else None,
        "results": results if isinstance(results, dict) else {}
    }


def _create_dag_for_mode(mode: str, task: str, config: Dict[str, Any]) -> Dict:
    """Create DAG structure for visualization (Stage 7)."""
    if mode == "one-shot":
        return {
            "nodes": [
                {"id": "start", "label": "Start", "type": "start", "status": "pending"},
                {"id": "execute", "label": "Execute", "type": "agent", "status": "pending"},
                {"id": "end", "label": "End", "type": "end", "status": "pending"}
            ],
            "edges": [
                {"source": "start", "target": "execute"},
                {"source": "execute", "target": "end"}
            ]
        }
    elif mode in ("planning-control", "idea-generation"):
        return {
            "nodes": [
                {"id": "start", "label": "Start", "type": "start", "status": "pending"},
                {"id": "planning", "label": "Planning", "type": "phase", "status": "pending"},
                {"id": "end", "label": "End", "type": "end", "status": "pending"}
            ],
            "edges": [
                {"source": "start", "target": "planning"},
                {"source": "planning", "target": "end"}
            ]
        }
    elif mode in ("ocr", "arxiv", "enhance-input"):
        return {
            "nodes": [
                {"id": "start", "label": "Start", "type": "start", "status": "pending"},
                {"id": "execute", "label": mode.replace("-", " ").title(), "type": "agent", "status": "pending"},
                {"id": "end", "label": "End", "type": "end", "status": "pending"}
            ],
            "edges": [
                {"source": "start", "target": "execute"},
                {"source": "execute", "target": "end"}
            ]
        }
    # Fallback
    return {
        "nodes": [
            {"id": "start", "label": "Start", "type": "start", "status": "pending"},
            {"id": "execute", "label": "Execute", "type": "agent", "status": "pending"},
            {"id": "end", "label": "End", "type": "end", "status": "pending"}
        ],
        "edges": [
            {"source": "start", "target": "execute"},
            {"source": "execute", "target": "end"}
        ]
    }


# ---------------------------------------------------------------------------
# Global executor instance
# ---------------------------------------------------------------------------

_executor: Optional[IsolatedTaskExecutor] = None


def get_isolated_executor() -> IsolatedTaskExecutor:
    """Get or create global isolated executor."""
    global _executor
    if _executor is None:
        _executor = IsolatedTaskExecutor(max_workers=10)
    return _executor
