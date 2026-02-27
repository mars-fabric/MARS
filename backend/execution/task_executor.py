"""
CMBAgent task execution logic.

Session management (Stages 10-11):
- session_id is passed via config from websocket handler
- Session state is saved on phase changes and completion for ALL modes
- Supports pause/resume/continuation via SessionManager
"""

import asyncio
import concurrent.futures
import contextvars
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import WebSocket

from core.config import settings
from core.logging import get_logger
from websocket.events import send_ws_event
from execution.stream_capture import StreamCapture, AG2IOStreamCapture
from execution.dag_tracker import DAGTracker
from execution.isolated_executor import get_isolated_executor
from backend.loggers import LoggerFactory

logger = get_logger(__name__)

# Feature flag for gradual rollout (Stage 6)
# Set to True to use process-based isolation for non-HITL modes
USE_ISOLATED_EXECUTION = True

# Services will be loaded at runtime
_services_available = None
_workflow_service = None
_execution_service = None
_session_manager_loaded = False
_session_manager = None


def _check_services():
    """Check if services are available and load them."""
    global _services_available, _workflow_service, _execution_service
    if _services_available is None:
        try:
            from services import workflow_service, execution_service
            _workflow_service = workflow_service
            _execution_service = execution_service
            _services_available = True
        except ImportError:
            _services_available = False
    return _services_available


def _get_session_manager():
    """Get session manager instance (lazy load)."""
    global _session_manager_loaded, _session_manager
    if not _session_manager_loaded:
        try:
            from services.session_manager import get_session_manager
            _session_manager = get_session_manager()
        except ImportError:
            _session_manager = None
        _session_manager_loaded = True
    return _session_manager


async def execute_cmbagent_task(
    websocket: WebSocket,
    task_id: str,
    task: str,
    config: Dict[str, Any]
):
    """Execute CMBAgent task with real-time output streaming.

    Uses isolated subprocess execution for utility modes (Stage 6)
    to prevent global state pollution between concurrent tasks.

    Production modes (one-shot, planning-control, HITL, etc.) use
    in-process execution with full tracking infrastructure:
    DAGTracker, CostCollector, EventRepository, FileRepository.

    Session management (Stages 10-11):
    - session_id is extracted from config (created by websocket handler)
    - Session state is saved on phase changes and at completion
    - Sessions are completed or suspended based on outcome

    Integrates with:
    - Stage 3: State Machine (pause/resume/cancel via workflow_service)
    - Stage 5: WebSocket Protocol (standardized events)
    - Stage 6: Process-based isolation
    - Stage 7: Output channel routing
    - Stages 10-11: Session management for all modes
    """
    mode = config.get("mode", "one-shot")

    # Modes that require in-process execution with full tracking:
    # - HITL modes need bidirectional communication (approval queues)
    # - All production modes need DAGTracker, CostCollector, EventRepository,
    #   and FileRepository which only exist in the in-process path
    tracked_modes = {
        "copilot", "hitl-interactive",          # HITL: bidirectional comms
        "planning-control", "idea-generation",  # Need dynamic DAG + full tracking
        "deep-research-extended",               # Need dynamic DAG + full tracking
        "one-shot",                             # Need DAG + cost + file tracking
    }

    if USE_ISOLATED_EXECUTION and mode not in tracked_modes:
        logger.info("Task %s using isolated execution (mode=%s)", task_id, mode)
        await _execute_isolated(websocket, task_id, task, config)
        return

    if mode in tracked_modes:
        logger.info("Task %s using tracked in-process execution (mode=%s)", task_id, mode)
    else:
        logger.info("Task %s using in-process execution (isolated disabled)", task_id)

    # Fall through to legacy execution
    services_available = _check_services()

    # Session tracking for ALL modes (Stages 10-11)
    session_id = config.get("session_id")
    session_manager = _get_session_manager()
    conversation_buffer = []  # Track messages for session state

    # Save user task as first conversation entry
    if session_id and task:
        conversation_buffer.append({
            "role": "user",
            "content": task[:2000],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Get work directory from config or use default from settings
    work_dir = config.get("workDir", settings.default_work_dir)
    if work_dir.startswith("~"):
        work_dir = os.path.expanduser(work_dir)

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

    # Set up environment variables
    os.environ["CMBAGENT_DEBUG"] = "false"
    os.environ["CMBAGENT_DISABLE_DISPLAY"] = "true"

    dag_tracker = None

    try:
        logger.debug("Legacy execute_cmbagent_task: task_id=%s, mode=%s", task_id, mode)

        await send_ws_event(
            websocket, "status",
            {"message": "Initializing CMBAgent..."},
            run_id=task_id,
            session_id=session_id
        )

        # Import cmbagent
        import cmbagent
        from cmbagent.utils import get_api_keys_from_env

        api_keys = get_api_keys_from_env()

        # Map frontend config to CMBAgent parameters (mode already set above)
        engineer_model = config.get("model", "gpt-4o")
        max_rounds = config.get("maxRounds", 25)
        max_attempts = config.get("maxAttempts", 6)
        agent = config.get("agent", "engineer")
        default_formatter_model = config.get("defaultFormatterModel", "o3-mini-2025-01-31")
        default_llm_model = config.get("defaultModel", "gpt-4.1-2025-04-14")

        # Get run_id from workflow service if available
        db_run_id = None
        if services_available:
            run_info = _workflow_service.get_run_info(task_id)
            if run_info:
                db_run_id = run_info.get("db_run_id")

        # Get event loop early - needed by DAGTracker and StreamCapture
        loop = asyncio.get_event_loop()

        # Create DAG tracker for this execution
        dag_tracker = DAGTracker(
            websocket, task_id, mode, send_ws_event, run_id=db_run_id,
            session_id=session_id, event_loop=loop
        )
        dag_data = dag_tracker.create_dag_for_mode(task, config)
        effective_run_id = dag_tracker.run_id or task_id

        # Create CostCollector for JSON-based cost tracking
        from backend.execution.cost_collector import CostCollector
        cost_collector = CostCollector(
            db_session=dag_tracker.db_session,
            session_id=session_id or dag_tracker.session_id or "",
            run_id=effective_run_id,
        )

        # Set initial phase based on mode
        if mode in ["planning-control", "idea-generation", "hitl-interactive", "copilot", "deep-research-extended"]:
            dag_tracker.set_phase("planning", None)
        else:
            dag_tracker.set_phase("execution", None)

        # Emit DAG created event
        await send_ws_event(
            websocket,
            "dag_created",
            {
                "run_id": effective_run_id,
                "nodes": dag_tracker.nodes,
                "edges": dag_tracker.edges,
                "levels": dag_data.get("levels", 1)
            },
            run_id=effective_run_id,
            session_id=session_id
        )

        # Planning & Control specific parameters
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        researcher_model = config.get("researcherModel", "gpt-4.1-2025-04-14")
        max_plan_steps = config.get("maxPlanSteps", 10)
        n_plan_reviews = config.get("nPlanReviews", 1)
        plan_instructions = config.get("planInstructions", "")

        # Idea Generation specific parameters
        idea_maker_model = config.get("ideaMakerModel", "gpt-4.1-2025-04-14")
        idea_hater_model = config.get("ideaHaterModel", "o3-mini-2025-01-31")

        # OCR specific parameters
        save_markdown = config.get("saveMarkdown", True)
        save_json = config.get("saveJson", True)
        save_text = config.get("saveText", False)
        max_workers = config.get("maxWorkers", 4)
        ocr_output_dir = config.get("ocrOutputDir", None)

        await send_ws_event(
            websocket, "output",
            {"message": f"🚀 Starting CMBAgent in {mode.replace('-', ' ').title()} mode"},
            run_id=task_id,
            session_id=session_id
        )
        await send_ws_event(
            websocket, "output",
            {"message": f"📋 Task: {task}"},
            run_id=task_id,
            session_id=session_id
        )

        # Emit workflow_started so the frontend resets cost/file/timeline state
        await send_ws_event(
            websocket, "workflow_started",
            {
                "run_id": effective_run_id,
                "task_description": task[:200],
                "mode": mode,
                "agent": agent,
                "model": engineer_model,
            },
            run_id=effective_run_id,
            session_id=session_id
        )

        # Update first node to running
        first_node = dag_tracker.get_first_node()
        if first_node:
            await dag_tracker.update_node_status(first_node, "running")

        # Log mode-specific configuration
        if mode == "planning-control":
            await send_ws_event(
                websocket, "output",
                {"message": f"Configuration: Planner={planner_model}, Engineer={engineer_model}"},
                run_id=task_id,
                session_id=session_id
            )
        elif mode == "idea-generation":
            await send_ws_event(
                websocket, "output",
                {"message": f"Configuration: Idea Maker={idea_maker_model}, Idea Hater={idea_hater_model}"},
                run_id=task_id,
                session_id=session_id
            )
        elif mode == "ocr":
            await send_ws_event(
                websocket, "output",
                {"message": f"Configuration: Save Markdown={save_markdown}, Max Workers={max_workers}"},
                run_id=task_id,
                session_id=session_id
            )
        elif mode == "copilot":
            await send_ws_event(
                websocket, "output",
                {"message": f"Configuration: Agents={config.get('availableAgents', ['engineer', 'researcher'])}, Planning={config.get('enablePlanning', True)}"},
                run_id=task_id,
                session_id=session_id
            )
        elif mode == "hitl-interactive":
            await send_ws_event(
                websocket, "output",
                {"message": f"Configuration: Variant={config.get('hitlVariant', 'full_interactive')}, Engineer={engineer_model}"},
                run_id=task_id,
                session_id=session_id
            )
        elif mode == "one-shot":
            await send_ws_event(
                websocket, "output",
                {"message": f"Configuration: Agent={agent}, Model={engineer_model}"},
                run_id=task_id,
                session_id=session_id
            )

        start_time = time.time()

        # Create run and session loggers for segregated logging
        run_logger, session_logger, legacy_symlink = LoggerFactory.create_loggers(
            session_id=session_id,
            run_id=task_id,
            work_dir=work_dir,
            task_work_dir=task_work_dir  # Nested under session/tasks/{task_id}
        )

        # Log run started to BOTH files
        await run_logger.write("run.started", "",
            mode=mode, agent=agent,
            model=engineer_model, work_dir=task_work_dir)
        await session_logger.write("run.started", f"[{task_id}]",
            mode=mode, agent=agent,
            model=engineer_model, work_dir=task_work_dir)

        # Create stream capture (relay only - no detection logic)
        stream_capture = StreamCapture(
            websocket, task_id, send_ws_event,
            loop=loop, work_dir=task_work_dir, session_id=session_id,
            run_logger=run_logger, session_logger=session_logger
        )

        # Create callbacks
        from cmbagent.callbacks import (
            merge_callbacks,
            create_print_callbacks, WorkflowCallbacks
        )
        from backend.callbacks import create_websocket_callbacks

        def ws_send_event(event_type: str, data: Dict[str, Any]):
            """Send WebSocket event from sync context."""
            try:
                future = asyncio.run_coroutine_threadsafe(
                    send_ws_event(websocket, event_type, data, run_id=task_id, session_id=session_id),
                    loop
                )
                try:
                    result = future.result(timeout=10.0)
                    if not result:
                        logger.warning("ws_send_event: %s send returned False (connection may be closed)", event_type)
                except TimeoutError:
                    logger.warning("ws_send_event: %s not confirmed within 10s", event_type)
                except Exception as e:
                    logger.error("ws_send_event: %s failed: %s", event_type, e)
            except Exception as e:
                logger.error("ws_send_event: failed to queue %s: %s", event_type, e)

        def sync_pause_check():
            """Synchronous pause check - blocks while paused."""
            if services_available:
                while _execution_service.is_paused(task_id):
                    if _execution_service.is_cancelled(task_id):
                        raise Exception("Workflow cancelled by user")
                    time.sleep(0.5)

        def should_continue():
            """Check if workflow should continue."""
            if services_available:
                if _execution_service.is_cancelled(task_id):
                    return False
            return True

        # Determine HITL mode for proper DAG node handling
        hitl_mode = None
        if mode == "hitl-interactive":
            hitl_mode = config.get("hitlVariant", "full_interactive")

        ws_callbacks = create_websocket_callbacks(ws_send_event, task_id, hitl_mode=hitl_mode)

        # Create execution event tracking callbacks
        def create_execution_event(event_type: str, agent_name: str, **kwargs):
            """Helper to create ExecutionEvent from callbacks"""
            if dag_tracker and dag_tracker.event_repo and dag_tracker.db_session:
                try:
                    from datetime import datetime, timezone as tz
                    dag_tracker.execution_order_counter += 1

                    current_node_id = None
                    for node_id, status in dag_tracker.node_statuses.items():
                        if status == "running":
                            current_node_id = node_id
                            break

                    dag_tracker._persist_dag_nodes_to_db()

                    # Get current phase and step from DAGTracker
                    current_phase = dag_tracker.get_current_phase()
                    current_step = dag_tracker.get_current_step_number()

                    # Add phase info to meta
                    meta = kwargs.pop('meta', {}) or {}
                    meta['workflow_phase'] = current_phase
                    if current_step is not None:
                        meta['step_number'] = current_step

                    dag_tracker.event_repo.create_event(
                        run_id=dag_tracker.run_id,
                        node_id=current_node_id,
                        event_type=event_type,
                        execution_order=dag_tracker.execution_order_counter,
                        agent_name=agent_name,
                        meta=meta,
                        **kwargs
                    )
                except Exception as e:
                    logger.error("Error creating %s event: %s", event_type, e)
                    if dag_tracker.db_session:
                        dag_tracker.db_session.rollback()

        def on_agent_msg(agent, role, content, metadata):
            import re
            try:
                # Track message in conversation buffer for session state (Stages 10-11)
                if session_id and content:
                    conversation_buffer.append({
                        "role": role or "assistant",
                        "agent": agent,
                        "content": content[:2000] if content else "",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    # Cap buffer to prevent unbounded growth (Stage 11B Issue 6)
                    if len(conversation_buffer) > 200:
                        conversation_buffer[:] = conversation_buffer[-100:]

                code_blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', content) if content else []
                create_execution_event(
                    event_type="agent_call",
                    agent_name=agent,
                    event_subtype="message",
                    status="completed",
                    inputs={"role": role, "message": content[:500] if content else ""},
                    outputs={"full_content": content[:3000] if content else ""},
                    meta={"has_code": len(code_blocks) > 0, **(metadata or {})}
                )
            except Exception as e:
                logger.error("Error in on_agent_msg callback: %s", e)

        def on_code_exec(agent, code, language, result):
            try:
                create_execution_event(
                    event_type="code_exec",
                    agent_name=agent,
                    event_subtype="executed",
                    status="completed" if result and "error" not in str(result).lower() else "failed",
                    inputs={"language": language, "code": code[:2000] if code else ""},
                    outputs={"result": result[:2000] if result else None},
                    meta={"language": language}
                )
            except Exception as e:
                logger.error("Error in on_code_exec callback: %s", e)

        def on_tool(agent, tool_name, arguments, result):
            try:
                import json
                args_str = json.dumps(arguments, default=str)[:500] if isinstance(arguments, dict) else str(arguments)[:500]
                create_execution_event(
                    event_type="tool_call",
                    agent_name=agent,
                    event_subtype="invoked",
                    status="completed" if result else "failed",
                    inputs={"tool": tool_name, "args": args_str},
                    outputs={"result": str(result)[:2000] if result else None},
                    meta={"tool_name": tool_name}
                )
            except Exception as e:
                logger.error("Error in on_tool callback: %s", e)

        def on_phase_change(phase: str, step_number: int = None):
            """Handle phase change events from the workflow"""
            if dag_tracker:
                dag_tracker.set_phase(phase, step_number)
                logger.debug("Phase changed to: %s, step: %s", phase, step_number)

                # One-shot DAG node transitions:
                # When the one_shot phase starts executing, mark init → completed
                # and execute → running so the UI shows real-time progress.
                if phase == "one_shot" and mode == "one-shot":
                    try:
                        asyncio.run_coroutine_threadsafe(
                            dag_tracker.update_node_status("init", "completed"), loop
                        ).result(timeout=5.0)
                        asyncio.run_coroutine_threadsafe(
                            dag_tracker.update_node_status("execute", "running"), loop
                        ).result(timeout=5.0)
                    except Exception as e:
                        logger.warning("Failed to update one-shot DAG nodes: %s", e)

            # Save session state on phase change for ALL modes (Stages 10-11)
            if session_manager and session_id:
                try:
                    session_manager.save_session_state(
                        session_id=session_id,
                        conversation_history=conversation_buffer[-100:],
                        current_phase=phase,
                        current_step=step_number,
                    )
                except Exception as e:
                    logger.warning("Failed to save session state on phase change: %s", e)

        def on_planning_complete_tracking(plan_info):
            """Track files and sync DAGTracker after planning phase completes"""
            if dag_tracker:
                # Sync DAGTracker internal state with the dynamically added step nodes
                # This ensures DAGTracker.nodes stays consistent for subsequent updates
                if plan_info and plan_info.steps:
                    asyncio.run_coroutine_threadsafe(
                        dag_tracker.add_step_nodes(plan_info.steps), loop
                    ).result(timeout=5.0)
                    # Mark planning as completed in tracker
                    asyncio.run_coroutine_threadsafe(
                        dag_tracker.update_node_status("planning", "completed"), loop
                    ).result(timeout=5.0)
                    # Note: Human review is tracked as events within the planning phase, not a separate node
                # Track files created during planning (explicit phase, not guessed)
                dag_tracker.track_files_in_work_dir(
                    task_work_dir, "planning",
                    workflow_phase="planning",
                )
                logger.debug("Tracked planning files and synced DAG")

        def on_step_start_tracking(step_info):
            """Update DAGTracker when step starts"""
            if dag_tracker:
                step_node_id = f"step_{step_info.step_number}"
                asyncio.run_coroutine_threadsafe(
                    dag_tracker.update_node_status(step_node_id, "running"), loop
                ).result(timeout=5.0)

        def on_step_complete_tracking(step_info):
            """Track files and update DAGTracker after each step completes"""
            if dag_tracker:
                step_node_id = f"step_{step_info.step_number}"
                asyncio.run_coroutine_threadsafe(
                    dag_tracker.update_node_status(step_node_id, "completed", work_dir=task_work_dir), loop
                ).result(timeout=5.0)
                dag_tracker.track_files_in_work_dir(
                    task_work_dir, step_node_id,
                    workflow_phase="control",
                    generating_agent=getattr(step_info, 'agent', None) or "engineer",
                )
                logger.debug("Tracked files for step %s", step_info.step_number)

        def on_step_failed_tracking(step_info):
            """Update DAGTracker when step fails"""
            if dag_tracker:
                step_node_id = f"step_{step_info.step_number}"
                asyncio.run_coroutine_threadsafe(
                    dag_tracker.update_node_status(step_node_id, "failed", error=step_info.error), loop
                ).result(timeout=5.0)

        def on_cost_update_tracking(cost_data):
            """Route cost data to CostCollector for DB persistence and WS emission."""
            cost_collector.collect_from_callback(cost_data, ws_send_func=ws_send_event)

        event_tracking_callbacks = WorkflowCallbacks(
            on_agent_message=on_agent_msg,
            on_code_execution=on_code_exec,
            on_tool_call=on_tool,
            on_phase_change=on_phase_change,
            on_planning_complete=on_planning_complete_tracking,
            on_step_start=on_step_start_tracking,
            on_step_complete=on_step_complete_tracking,
            on_step_failed=on_step_failed_tracking,
            on_cost_update=on_cost_update_tracking,
        )

        pause_callbacks = WorkflowCallbacks(
            should_continue=should_continue,
            on_pause_check=sync_pause_check
        )

        workflow_callbacks = merge_callbacks(
            ws_callbacks, create_print_callbacks(),
            pause_callbacks, event_tracking_callbacks
        )

        def run_cmbagent():
            """Execute CMBAgent in thread pool"""
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            # For HITL/copilot modes, suppress stdout to prevent logs
            # from leaking to the main terminal - route only to WebSocket
            # Suppress stdout for all modes to prevent agent logs in terminal
            # All output is captured and sent to WebSocket + log files
            suppress_stdout = True

            class StreamWrapper:
                def __init__(self, original, capture, loop, suppress=False):
                    self.original = original
                    self.capture = capture
                    self.loop = loop
                    self.suppress = suppress

                def write(self, text):
                    if self.original and not self.suppress:
                        self.original.write(text)
                    if text.strip():
                        asyncio.run_coroutine_threadsafe(
                            self.capture.write(text), self.loop
                        )
                    return len(text)

                def flush(self):
                    if self.original and not self.suppress:
                        self.original.flush()

                def fileno(self):
                    """Return file descriptor if available, otherwise raise AttributeError"""
                    if hasattr(self.original, 'fileno'):
                        return self.original.fileno()
                    raise AttributeError("fileno not available")

                def isatty(self):
                    return False

            try:
                sys.stdout = StreamWrapper(original_stdout, stream_capture, loop, suppress=suppress_stdout)
                sys.stderr = StreamWrapper(original_stderr, stream_capture, loop, suppress=suppress_stdout)

                import builtins
                original_print = builtins.print

                def custom_print(*args, **kwargs):
                    output = " ".join(str(arg) for arg in args)
                    asyncio.run_coroutine_threadsafe(
                        stream_capture.write(output + "\n"), loop
                    )
                    if original_stdout and not suppress_stdout:
                        original_stdout.write(output + "\n")
                        original_stdout.flush()

                builtins.print = custom_print

                # Set up AG2 IOStream capture
                try:
                    from autogen.io.base import IOStream
                    ag2_iostream = AG2IOStreamCapture(
                        websocket, task_id, send_ws_event, loop,
                        session_id=session_id, session_logger=session_logger
                    )
                    IOStream.set_global_default(ag2_iostream)
                except Exception as e:
                    logger.warning("Could not set AG2 IOStream: %s", e)

                # Resolve db_factory for approval manager persistence (Stage 11C)
                try:
                    from cmbagent.database.base import get_db_session
                    _approval_db_factory = get_db_session
                except ImportError:
                    _approval_db_factory = None

                # Execute based on mode
                if mode == "planning-control":
                    # Pure planning → control, NO approval gates.
                    # For HITL approval, use "hitl-interactive" mode instead.
                    logger.info("Using phase-based workflow for planning-control")

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
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model,
                        callbacks=workflow_callbacks,
                    )
                elif mode == "hitl-interactive":
                    # HITL Interactive mode - full human-in-the-loop workflow
                    from cmbagent.workflows import hitl_workflow
                    from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

                    # Get HITL-specific config
                    hitl_variant = config.get("hitlVariant", "full_interactive")
                    max_human_iterations = config.get("maxHumanIterations", 3)
                    approval_mode = config.get("approvalMode", "both")
                    allow_plan_modification = config.get("allowPlanModification", True)
                    allow_step_skip = config.get("allowStepSkip", True)
                    allow_step_retry = config.get("allowStepRetry", True)
                    show_step_context = config.get("showStepContext", True)

                    # Create WebSocket-based approval manager for UI interaction
                    hitl_approval_manager = WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)
                    logger.info("HITL workflow variant: %s", hitl_variant)

                    # Select workflow based on variant
                    if hitl_variant == "planning_only":
                        results = hitl_workflow.hitl_planning_only_workflow(
                            task=task,
                            max_rounds_planning=50,
                            max_rounds_control=max_rounds,
                            max_plan_steps=max_plan_steps,
                            max_human_iterations=max_human_iterations,
                            n_plan_reviews=n_plan_reviews,
                            allow_plan_modification=allow_plan_modification,
                            planner_model=planner_model,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            default_formatter_model=default_formatter_model,
                            default_llm_model=default_llm_model,
                            callbacks=workflow_callbacks,
                            approval_manager=hitl_approval_manager,
                        )
                    elif hitl_variant == "error_recovery":
                        results = hitl_workflow.hitl_error_recovery_workflow(
                            task=task,
                            max_rounds_planning=50,
                            max_rounds_control=max_rounds,
                            max_plan_steps=max_plan_steps,
                            n_plan_reviews=n_plan_reviews,
                            max_n_attempts=max_attempts,
                            allow_step_retry=allow_step_retry,
                            allow_step_skip=allow_step_skip,
                            planner_model=planner_model,
                            plan_reviewer_model=plan_reviewer_model,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            default_formatter_model=default_formatter_model,
                            default_llm_model=default_llm_model,
                            callbacks=workflow_callbacks,
                            approval_manager=hitl_approval_manager,
                        )
                    else:  # full_interactive (default)
                        results = hitl_workflow.hitl_interactive_workflow(
                            task=task,
                            max_rounds_control=max_rounds,
                            max_n_attempts=max_attempts,
                            max_plan_steps=max_plan_steps,
                            max_human_iterations=max_human_iterations,
                            n_plan_reviews=n_plan_reviews,
                            approval_mode=approval_mode,
                            allow_plan_modification=allow_plan_modification,
                            allow_step_skip=allow_step_skip,
                            allow_step_retry=allow_step_retry,
                            show_step_context=show_step_context,
                            planner_model=planner_model,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            default_formatter_model=default_formatter_model,
                            default_llm_model=default_llm_model,
                            callbacks=workflow_callbacks,
                            approval_manager=hitl_approval_manager,
                        )
                elif mode == "copilot":
                    # Copilot mode - flexible assistant that adapts to task complexity
                    from cmbagent.workflows.copilot import copilot, continue_copilot_sync
                    from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

                    # Check if this is a continuation of an existing session
                    existing_session_id = config.get("copilotSessionId")
                    
                    if existing_session_id:
                        # Continue existing session
                        logger.info("Continuing copilot session: %s", existing_session_id)
                        copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)
                        
                        try:
                            results = continue_copilot_sync(
                                session_id=existing_session_id,
                                additional_context=task,
                                approval_manager=copilot_approval_manager,
                            )
                        except Exception as e:
                            logger.warning("Session continuation failed: %s, starting new session", e)
                            existing_session_id = None  # Fall through to new session

                    if not existing_session_id:
                        # Get copilot-specific config
                        available_agents = config.get("availableAgents", ["engineer", "researcher"])
                        enable_planning = config.get("enablePlanning", True)
                        use_dynamic_routing = config.get("useDynamicRouting", True)
                        complexity_threshold = config.get("complexityThreshold", 50)
                        continuous_mode = config.get("continuousMode", False)
                        copilot_approval_mode = config.get("approvalMode", "after_step")
                        conversational = config.get("conversational", False) or copilot_approval_mode == "conversational"
                        control_model = config.get("controlModel", planner_model)  # Use planner model as default
                        tool_approval = config.get("toolApproval", "none")  # "prompt" | "auto_allow_all" | "none"
                        intelligent_routing = config.get("intelligentRouting", "balanced")  # "aggressive" | "balanced" | "minimal"

                        # Create WebSocket-based approval manager for HITL interactions
                        copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)
                        logger.info("Copilot config: agents=%s, planning=%s, dynamic_routing=%s, continuous=%s, tool_approval=%s",
                                    available_agents, enable_planning, use_dynamic_routing, continuous_mode, tool_approval)

                        # Run copilot workflow (synchronous - runs in ThreadPoolExecutor)
                        results = copilot(
                            task=task,
                            available_agents=available_agents,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            planner_model=planner_model,
                            control_model=control_model,
                            enable_planning=enable_planning,
                            use_dynamic_routing=use_dynamic_routing,
                            complexity_threshold=complexity_threshold,
                            continuous_mode=continuous_mode,
                            max_turns=config.get("maxTurns", 20),
                            max_rounds=max_rounds,
                            max_plan_steps=max_plan_steps,
                            max_n_attempts=max_attempts,
                            approval_mode=copilot_approval_mode,
                            conversational=conversational,
                            tool_approval=tool_approval,
                            intelligent_routing=intelligent_routing,
                            auto_approve_simple=config.get("autoApproveSimple", True),
                            engineer_instructions=config.get("engineerInstructions", ""),
                            researcher_instructions=config.get("researcherInstructions", ""),
                            planner_instructions=plan_instructions,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            callbacks=workflow_callbacks,
                            approval_manager=copilot_approval_manager,
                        )
                elif mode == "idea-generation":
                    # Always using phase-based workflow
                    logger.info("Using phase-based workflow for idea-generation")
                    
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
                        work_dir=task_work_dir,
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

                    if not os.path.exists(pdf_path):
                        raise ValueError(f"Path does not exist: {pdf_path}")

                    output_dir = ocr_output_dir if ocr_output_dir and ocr_output_dir.strip() else None

                    if os.path.isfile(pdf_path):
                        results = cmbagent.process_single_pdf(
                            pdf_path=pdf_path,
                            save_markdown=save_markdown,
                            save_json=save_json,
                            save_text=save_text,
                            output_dir=output_dir,
                            work_dir=task_work_dir,
                            callbacks=workflow_callbacks,
                        )
                    elif os.path.isdir(pdf_path):
                        results = cmbagent.process_folder(
                            folder_path=pdf_path,
                            save_markdown=save_markdown,
                            save_json=save_json,
                            save_text=save_text,
                            output_dir=output_dir,
                            max_workers=max_workers,
                            work_dir=task_work_dir
                        )
                    else:
                        raise ValueError(f"Path is neither a file nor a directory: {pdf_path}")
                elif mode == "arxiv":
                    results = cmbagent.arxiv_filter(
                        input_text=task,
                        work_dir=task_work_dir,
                        callbacks=workflow_callbacks,
                    )
                elif mode == "enhance-input":
                    results = cmbagent.preprocess_task(
                        text=task,
                        work_dir=task_work_dir,
                        max_workers=max_workers,
                        clear_work_dir=False,
                        callbacks=workflow_callbacks,
                    )
                elif mode == "deep-research-extended":
                    from cmbagent.workflows.composer import get_workflow, WorkflowExecutor

                    workflow_def = get_workflow("deep_research_extended")
                    executor = WorkflowExecutor(
                        workflow=workflow_def,
                        task=task,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        callbacks=workflow_callbacks,
                    )
                    wf_context = executor.run_sync()
                    results = {
                        "chat_history": [],
                        "final_context": wf_context.shared_state,
                        "run_id": wf_context.run_id,
                        "total_time": wf_context.phase_timings.get("total", 0),
                    }
                    for r in executor.results:
                        results["chat_history"].extend(r.chat_history)
                else:
                    # One Shot mode
                    results = cmbagent.one_shot(
                        task=task,
                        max_rounds=max_rounds,
                        max_n_attempts=max_attempts,
                        engineer_model=engineer_model,
                        agent=agent,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model,
                        callbacks=workflow_callbacks,
                    )

                return results

            finally:
                builtins.print = original_print
                sys.stdout = original_stdout
                sys.stderr = original_stderr

        # Run CMBAgent in executor with contextvars propagation
        ctx = contextvars.copy_context()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(ctx.run, run_cmbagent)

            while not future.done():
                await asyncio.sleep(1)

                # Check if cancelled
                if services_available and _execution_service.is_cancelled(task_id):
                    logger.info("Task %s cancelled", task_id)
                    future.cancel()
                    await send_ws_event(
                        websocket, "workflow_cancelled",
                        {"message": "Workflow cancelled by user"},
                        run_id=task_id,
                        session_id=session_id
                    )
                    return

                # Check if paused
                if services_available:
                    await _execution_service.wait_if_paused(task_id)

                await send_ws_event(
                    websocket, "heartbeat",
                    {"timestamp": time.time()},
                    run_id=task_id,
                    session_id=session_id
                )

            results = future.result()

        execution_time = time.time() - start_time

        # Log run completion to BOTH files
        await run_logger.write("run.completed", "", status="success", execution_time=f"{execution_time:.2f}s")
        await session_logger.write("run.completed", f"[{task_id}]", status="success", execution_time=f"{execution_time:.2f}s")

        # Close stream capture log file
        if stream_capture and hasattr(stream_capture, 'close'):
            await stream_capture.close()

        # Update DAG nodes to completed status
        if dag_tracker and dag_tracker.node_statuses:
            for node_id in dag_tracker.node_statuses:
                if node_id != "terminator":
                    await dag_tracker.update_node_status(node_id, "completed")
                    dag_tracker.track_files_in_work_dir(task_work_dir, node_id)
            if "terminator" in dag_tracker.node_statuses:
                await dag_tracker.update_node_status("terminator", "completed")

        # Safety net: scan work_dir/cost/ for any cost JSONs not yet persisted
        # This catches cases where the callback-based path silently failed
        if cost_collector:
            try:
                cost_collector.collect_from_work_dir(task_work_dir)
            except Exception as e:
                logger.warning("Cost collect_from_work_dir failed: %s", e)

        # Mark workflow as completed
        if services_available:
            _workflow_service.complete_workflow(task_id)

        # Complete session for ALL modes (Stages 10-11)
        if session_manager and session_id:
            try:
                session_manager.save_session_state(
                    session_id=session_id,
                    conversation_history=conversation_buffer,
                    current_phase="completed",
                )
                session_manager.complete_session(session_id)
                logger.info("Session %s completed for task %s", session_id, task_id)
            except Exception as e:
                logger.warning("Failed to complete session: %s", e)

        await send_ws_event(
            websocket, "output",
            {"message": f"✅ Task completed in {execution_time:.2f} seconds"},
            run_id=task_id,
            session_id=session_id
        )

        await send_ws_event(
            websocket, "result",
            {
                "execution_time": execution_time,
                "chat_history": getattr(results, 'chat_history', []) if hasattr(results, 'chat_history') else [],
                "final_context": getattr(results, 'final_context', {}) if hasattr(results, 'final_context') else {},
                "session_id": session_id or (results.get('session_id') if isinstance(results, dict) else None),
                "work_dir": task_work_dir,
                "base_work_dir": work_dir,
                "mode": mode
            },
            run_id=task_id,
            session_id=session_id
        )

        await send_ws_event(
            websocket, "workflow_completed",
            {
                "run_id": effective_run_id,
                "execution_time": execution_time,
                "mode": mode,
            },
            run_id=effective_run_id,
            session_id=session_id
        )

        await send_ws_event(
            websocket, "complete",
            {"message": "Task execution completed successfully"},
            run_id=task_id,
            session_id=session_id
        )

        # Close DAG tracker DB session
        if dag_tracker:
            dag_tracker.close()

    except Exception as e:
        error_msg = f"Error executing CMBAgent task: {str(e)}"
        logger.error(error_msg)

        # Log run failure to BOTH files
        await run_logger.write("run.failed", "", error=str(e))
        await session_logger.write("run.failed", f"[{task_id}]", error=str(e))

        # Close stream capture log file on error
        if stream_capture and hasattr(stream_capture, 'close'):
            await stream_capture.close()

        if dag_tracker and dag_tracker.node_statuses:
            for node_id in dag_tracker.node_statuses:
                await dag_tracker.update_node_status(node_id, "failed", error=error_msg)

        # Safety net: persist any cost data written before the failure
        if cost_collector:
            try:
                cost_collector.collect_from_work_dir(task_work_dir)
            except Exception:
                pass  # Best-effort during error handling

        if services_available:
            _workflow_service.fail_workflow(task_id, error_msg)

        # Suspend session on failure for ALL modes (Stages 10-11)
        if session_manager and session_id:
            try:
                session_manager.save_session_state(
                    session_id=session_id,
                    conversation_history=conversation_buffer,
                    current_phase="failed",
                )
                session_manager.suspend_session(session_id)
                logger.info("Session %s suspended after failure for task %s", session_id, task_id)
            except Exception as se:
                logger.warning("Failed to suspend session: %s", se)

        await send_ws_event(
            websocket, "workflow_failed",
            {"error": error_msg, "run_id": task_id},
            run_id=task_id,
            session_id=session_id
        )

        await send_ws_event(
            websocket, "error",
            {"message": error_msg},
            run_id=task_id,
            session_id=session_id
        )

        # Close DAG tracker DB session on error
        if dag_tracker:
            dag_tracker.close()


# ---------------------------------------------------------------------------
# Stage 6: Isolated subprocess execution
# ---------------------------------------------------------------------------

async def _execute_isolated(
    websocket: WebSocket,
    task_id: str,
    task: str,
    config: Dict[str, Any]
):
    """Execute task in isolated subprocess (Stage 6).

    Provides true process isolation so concurrent tasks don't pollute
    each other's globals (builtins.print, sys.stdout, IOStream).

    Stage 7 enhancements:
    - Structured event routing (DAG, cost, phase events)
    - Session state tracking via conversation buffer
    - Periodic state saves on phase changes
    """
    services_available = _check_services()
    executor = get_isolated_executor()

    # Session tracking (Stage 7)
    session_id = config.get("session_id")
    session_manager = None
    if session_id:
        try:
            from services.session_manager import get_session_manager
            session_manager = get_session_manager()
        except Exception:
            pass

    conversation_buffer = []

    # Save user task as first conversation entry
    if session_id and task:
        conversation_buffer.append({
            "role": "user",
            "content": task[:2000],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    work_dir = config.get("workDir", settings.default_work_dir)
    if work_dir.startswith("~"):
        work_dir = os.path.expanduser(work_dir)

    # Create task directory nested under session (same as in-process path)
    # Structure: {work_dir}/sessions/{session_id}/tasks/{task_id}
    task_work_dir = os.path.join(work_dir, "sessions", session_id, "tasks", task_id)

    async def output_callback(event_type: str, data: Dict[str, Any]):
        """Forward subprocess output to WebSocket and track state (Stage 7)."""
        await send_ws_event(websocket, event_type, data, run_id=task_id, session_id=session_id)

        # Track conversation for session save (Stage 7)
        if session_id and event_type in ("output", "agent_message", "error", "cost_update"):
            if event_type == "agent_message":
                conversation_buffer.append({
                    "role": data.get("role", "assistant"),
                    "agent": data.get("agent", ""),
                    "content": (data.get("content") or data.get("message") or "")[:2000],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            elif event_type == "error":
                conversation_buffer.append({
                    "role": "system",
                    "agent": "system",
                    "content": f"Error: {data.get('message', 'Unknown error')}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            elif event_type == "cost_update":
                conversation_buffer.append({
                    "role": "system",
                    "agent": "cost_tracker",
                    "content": f"Cost: ${data.get('cost', 0):.4f} (model: {data.get('model', 'unknown')})",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:  # output
                conversation_buffer.append({
                    "role": "system",
                    "content": data.get("message", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            # Cap buffer to prevent unbounded growth (Stage 11B Issue 6)
            if len(conversation_buffer) > 200:
                conversation_buffer[:] = conversation_buffer[-100:]

        # Save session state on phase changes (Stage 7)
        if event_type == "phase_change" and session_manager and session_id:
            try:
                session_manager.save_session_state(
                    session_id=session_id,
                    conversation_history=conversation_buffer[-100:],
                    context_variables=data.get("context", {}),
                    current_phase=data.get("phase"),
                    current_step=data.get("step"),
                )
            except Exception as e:
                logger.warning("Failed to save session state: %s", e)

    try:
        result = await executor.execute(
            task_id=task_id,
            task=task,
            config=config,
            output_callback=output_callback,
            work_dir=work_dir,
            task_work_dir=task_work_dir  # Put run.log alongside cost/, data/, etc.
        )

        # Final session state save (Stage 7)
        if session_manager and session_id:
            try:
                session_manager.save_session_state(
                    session_id=session_id,
                    conversation_history=conversation_buffer,
                    context_variables=result.get("final_context", {}),
                    current_phase="completed",
                )
                session_manager.complete_session(session_id)
            except Exception as e:
                logger.warning("Failed to save final session state: %s", e)

        # Mark workflow as completed
        if services_available:
            _workflow_service.complete_workflow(task_id)

        # Send result and completion events
        await send_ws_event(websocket, "result", {
            "execution_time": result.get("execution_time", 0),
            "chat_history": result.get("chat_history", []),
            "final_context": result.get("final_context", {}),
            "session_id": result.get("session_id"),
            "work_dir": result.get("work_dir", ""),
            "base_work_dir": work_dir,
            "mode": result.get("mode", config.get("mode", "one-shot"))
        }, run_id=task_id, session_id=session_id)

        await send_ws_event(websocket, "complete", {
            "message": "Task execution completed successfully"
        }, run_id=task_id, session_id=session_id)

    except Exception as e:
        error_msg = f"Error executing CMBAgent task: {str(e)}"
        logger.error("Isolated execution failed for task %s: %s", task_id, e)

        # Save conversation and suspend session on failure (Stage 7)
        if session_manager and session_id:
            try:
                session_manager.save_session_state(
                    session_id=session_id,
                    conversation_history=conversation_buffer,
                    current_phase="failed",
                )
                session_manager.suspend_session(session_id)
            except Exception as se:
                logger.warning("Failed to save/suspend session on failure: %s", se)

        if services_available:
            _workflow_service.fail_workflow(task_id, error_msg)

        await send_ws_event(websocket, "error", {
            "message": error_msg,
            "error_type": type(e).__name__
        }, run_id=task_id, session_id=session_id)
