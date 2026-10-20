"""
COMPASS Phase 8 — Autonomous Workflow Orchestrator
Central coordinator for end-to-end DAG execution, long-running background tasks,
execution-generation fencing, crash recovery, and universal STOP per Section 12.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from backend.app.database import DatabaseManager, db
from backend.app.logging_config import logger
from planner.checkpoint_manager import CheckpointManager
from planner.execution_trace import ExecutionTraceManager
from planner.loop_detector import LoopDetector
from planner.resource_governor import ResourceGovernor, resource_governor
from planner.workflow_dag import (
    DAGValidationError,
    WorkflowDAGEngine,
    WorkflowDAGValidator,
)
from planner.workflow_models import (
    NodeState,
    ResourceBudget,
    RetryPolicy,
    Workflow,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeStatus,
    WorkflowState,
    WorkflowStatus,
    is_node_terminal,
    is_workflow_terminal,
)
from planner.workflow_scheduler import ReadyNodeScheduler, ResourceLockManager


class WorkflowOrchestrator:
    """
    Coordinates creation, validation, scheduling, execution, checkpointing,
    recovery, and termination of autonomous multi-step workflow graphs.
    """

    def __init__(
        self,
        *args,
        database: DatabaseManager | None = None,
        dag_validator: WorkflowDAGValidator | None = None,
        dag_engine: WorkflowDAGEngine | None = None,
        scheduler: ReadyNodeScheduler | None = None,
        lock_manager: ResourceLockManager | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        trace_manager: ExecutionTraceManager | None = None,
        governor: ResourceGovernor | None = None,
        loop_detector: LoopDetector | None = None,
        custom_node_executor: Callable[[WorkflowNode], tuple[bool, str | None, dict[str, Any] | None]] | None = None,
        **kwargs,
    ):
        if len(args) >= 1 and (hasattr(args[0], "validate_and_sort") or hasattr(args[0], "get_ready_nodes")):
            dag_engine = args[0]
            if len(args) >= 2:
                lock_manager = args[1]
            if len(args) >= 3:
                checkpoint_manager = args[2]
            database = None

        self.db = database or db
        self.dag_validator = dag_validator or WorkflowDAGValidator()
        self.dag_engine = dag_engine or WorkflowDAGEngine()
        self.lock_manager = lock_manager or ResourceLockManager()
        self.scheduler = scheduler or ReadyNodeScheduler(self.lock_manager)
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.trace_manager = trace_manager or ExecutionTraceManager()
        self.governor = governor or resource_governor
        self.loop_detector = loop_detector or LoopDetector()
        self.custom_node_executor = custom_node_executor

        self.dag = self.dag_engine
        self.checkpoints = self.checkpoint_manager
        self.action_registry: dict[str, Callable] = {}
        self.workflows: dict[str, Any] = {}
        self.stop_events: dict[str, Any] = {}

        self._active_workflows: dict[str, Workflow] = {}
        self._active_generations: dict[str, int] = {}
        self._active_threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._pause_events: dict[str, threading.Event] = {}
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._orchestrator_lock = threading.Lock()

    def register_action(self, action_name: str, handler: Callable) -> None:
        self.action_registry[action_name] = handler

    def submit_workflow(self, graph: Any) -> None:
        if hasattr(self.dag, "validate_and_sort"):
            self.dag.validate_and_sort(graph)
        import asyncio
        self.workflows[getattr(graph, "workflow_id", "")] = graph
        self.stop_events[getattr(graph, "workflow_id", "")] = asyncio.Event()
        graph.state = WorkflowStatus.READY


    def _save_state(self, graph: Any) -> None:
        if hasattr(self.checkpoints, "save_checkpoint") and hasattr(graph, "workflow_id"):
            state_dict = {
                "state": getattr(graph, "state", ""),
                "generation": getattr(graph, "generation", 0),
                "nodes": {nid: getattr(n, "state", getattr(n, "status", "")) for nid, n in getattr(graph, "nodes", {}).items()},
            }
            try:
                self.checkpoints.save_checkpoint(graph.workflow_id, state_dict)
            except Exception:
                pass

    async def _start_graph_workflow(self, workflow_id: str) -> None:
        graph = self.workflows.get(workflow_id)
        if not graph:
            raise ValueError(f"Workflow {workflow_id} not found")

        import asyncio
        graph.state = WorkflowStatus.RUNNING
        stop_event = self.stop_events.get(workflow_id)

        while getattr(graph, "state", None) == WorkflowStatus.RUNNING:
            if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
                graph.state = WorkflowStatus.CANCELLED
                break

            ready_nodes = self.dag.get_ready_nodes(graph)
            if not ready_nodes:
                all_completed = all(
                    getattr(n, "state", getattr(n, "status", None)) in (
                        WorkflowNodeStatus.COMPLETED,
                        WorkflowNodeStatus.SKIPPED,
                        "COMPLETED",
                        "SKIPPED",
                    )
                    for n in graph.nodes.values()
                )
                if all_completed:
                    graph.state = WorkflowStatus.COMPLETED
                    if hasattr(self.checkpoints, "clear_checkpoint"):
                        try:
                            self.checkpoints.clear_checkpoint(workflow_id)
                        except Exception:
                            pass
                    break

                has_failed = any(
                    getattr(n, "state", getattr(n, "status", None)) in (
                        WorkflowNodeStatus.FAILED,
                        "FAILED",
                    )
                    for n in graph.nodes.values()
                )
                if has_failed:
                    graph.state = WorkflowStatus.FAILED
                    break

                await asyncio.sleep(0.02)
                continue

            for node in ready_nodes:
                sched = getattr(self, "scheduler", None)
                can_sched = True
                nid = getattr(node, "id", getattr(node, "node_id", ""))
                if hasattr(sched, "can_schedule"):
                    can_sched = sched.can_schedule(nid)
                if can_sched:
                    if hasattr(sched, "mark_scheduled"):
                        sched.mark_scheduled(nid)
                    node.state = WorkflowNodeStatus.RUNNING
                    self._save_state(graph)
                    asyncio.create_task(self._execute_graph_node(graph, node))

            await asyncio.sleep(0.02)

    async def _execute_graph_node(self, graph: Any, node: Any) -> None:
        import asyncio
        current_gen = getattr(graph, "generation", 0)
        try:
            if current_gen != getattr(graph, "generation", 0):
                node.state = WorkflowNodeStatus.STOPPED
                return

            action_name = getattr(node, "action", "")
            if isinstance(action_name, dict):
                action_name = action_name.get("type", "")
            handler = self.action_registry.get(action_name)
            if not handler:
                raise ValueError(f"Action '{action_name}' not registered")

            locks = getattr(node, "required_locks", [])
            lm = getattr(self, "lock_manager", None)
            if lm and hasattr(lm, "acquire_locks") and locks:
                async with lm.acquire_locks(locks):
                    if current_gen != getattr(graph, "generation", 0):
                        node.state = WorkflowNodeStatus.STOPPED
                        return
                    if asyncio.iscoroutinefunction(handler):
                        await handler(getattr(node, "params", {}))
                    else:
                        handler(getattr(node, "params", {}))
            else:
                if current_gen != getattr(graph, "generation", 0):
                    node.state = WorkflowNodeStatus.STOPPED
                    return
                if asyncio.iscoroutinefunction(handler):
                    await handler(getattr(node, "params", {}))
                else:
                    handler(getattr(node, "params", {}))

            node.state = WorkflowNodeStatus.COMPLETED
        except Exception as e:
            node.state = WorkflowNodeStatus.FAILED
            try:
                from planner.reliability.diagnostics import emit_incident
                nid = getattr(node, "id", getattr(node, "node_id", ""))
                emit_incident(
                    workflow_id=getattr(graph, "workflow_id", ""),
                    node_id=nid,
                    exception=e,
                    severity="ERROR",
                )
            except Exception:
                pass
        finally:
            sched = getattr(self, "scheduler", None)
            nid = getattr(node, "id", getattr(node, "node_id", ""))
            if hasattr(sched, "mark_completed"):
                sched.mark_completed(nid)
            self._save_state(graph)


    # -----------------------------------------------------------------------
    # Event Emission
    # -----------------------------------------------------------------------

    def subscribe(
        self, workflow_id: str, callback: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Subscribe to workflow events for SSE or telemetry. Returns unsubscribe function."""
        with self._orchestrator_lock:
            if workflow_id not in self._subscribers:
                self._subscribers[workflow_id] = []
            self._subscribers[workflow_id].append(callback)

        def unsubscribe():
            with self._orchestrator_lock:
                if (
                    workflow_id in self._subscribers
                    and callback in self._subscribers[workflow_id]
                ):
                    self._subscribers[workflow_id].remove(callback)

        return unsubscribe

    def emit_event(
        self,
        workflow_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit workflow event to subscribers and trace manager."""
        event_dict = {
            "workflow_id": workflow_id,
            "event": event_type,
            "timestamp": time.time(),
            "payload": payload or {},
        }
        self.trace_manager.record_workflow_event(workflow_id, event_type, payload)

        callbacks: list[Callable[[dict[str, Any]], None]] = []
        with self._orchestrator_lock:
            callbacks = list(self._subscribers.get(workflow_id, []))

        for cb in callbacks:
            try:
                cb(event_dict)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    f"Error in event subscriber callback for [{workflow_id}]: {e}"
                )

    # -----------------------------------------------------------------------
    # Workflow Creation & Validation
    # -----------------------------------------------------------------------

    def create_workflow(
        self,
        goal: str,
        nodes: list[WorkflowNode],
        task_id: str | None = None,
        workflow_id: str | None = None,
        resource_budget: ResourceBudget | None = None,
        retry_policy: RetryPolicy | None = None,
        deadline: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        """
        Create, structurally validate, and persist a new workflow.
        Raises DAGValidationError if the graph is malformed.
        """
        wf_id = workflow_id or f"wf_{uuid.uuid4().hex[:12]}"
        t_id = task_id or f"task_{uuid.uuid4().hex[:12]}"

        # Bind all nodes to this workflow_id if not already bound
        for node in nodes:
            if not node.workflow_id:
                node.workflow_id = wf_id

        budget = resource_budget or ResourceBudget()
        policy = retry_policy or RetryPolicy()

        workflow = Workflow(
            workflow_id=wf_id,
            task_id=t_id,
            goal=goal,
            nodes=nodes,
            status=WorkflowStatus.CREATED,
            resource_budget=budget,
            retry_policy=policy,
            deadline=deadline,
            metadata=metadata or {},
            created_at=time.time(),
            updated_at=time.time(),
            execution_generation=1,
        )

        # Structural & semantic validation
        workflow.status = WorkflowStatus.VALIDATING
        is_valid, errors = self.dag_validator.validate(workflow)
        if not is_valid:
            workflow.status = WorkflowStatus.FAILED
            raise DAGValidationError(
                f"Workflow DAG validation failed: {'; '.join(errors)}"
            )

        workflow.status = WorkflowStatus.READY

        # Persist in DB
        try:
            self.db.create_workflow(
                {
                    "workflow_id": workflow.workflow_id,
                    "task_id": workflow.task_id,
                    "goal": workflow.goal,
                    "status": workflow.status.value,
                    "execution_generation": workflow.execution_generation,
                    "resource_budget": workflow.resource_budget.model_dump(),
                    "deadline": workflow.deadline,
                    "metadata": workflow.metadata,
                    "created_at": workflow.created_at,
                    "updated_at": workflow.updated_at,
                }
            )
            for node in workflow.nodes:
                self.db.upsert_workflow_node(
                    {
                        "node_id": node.node_id,
                        "workflow_id": workflow.workflow_id,
                        "goal": node.goal,
                        "status": node.status.value,
                        "dependencies": node.dependencies,
                        "attempt_count": node.attempt_count,
                        "created_at": node.created_at,
                        "updated_at": node.updated_at,
                        "metadata": node.model_dump(),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to persist workflow [{wf_id}] to database: {e}")

        # Start execution trace
        self.trace_manager.start_workflow_trace(wf_id, t_id, goal)

        with self._orchestrator_lock:
            self._active_workflows[wf_id] = workflow
            self._active_generations[wf_id] = 1
            self._stop_events[wf_id] = threading.Event()
            self._pause_events[wf_id] = threading.Event()

        self.emit_event(
            wf_id, "workflow_created", {"goal": goal, "node_count": len(nodes)}
        )
        return workflow

    # -----------------------------------------------------------------------
    # Execution Lifecycle (Start, Pause, Resume, Stop, Recover)
    # -----------------------------------------------------------------------

    def start_workflow(self, workflow_id: str, run_in_background: bool = True) -> Any:
        """Begin execution of a validated workflow."""
        if workflow_id in self.workflows:
            return self._start_graph_workflow(workflow_id)

        with self._orchestrator_lock:
            workflow = self._active_workflows.get(workflow_id)
            if not workflow:
                # Attempt to load from DB
                workflow = self._load_workflow_from_db(workflow_id)
                if not workflow:
                    logger.error(f"Cannot start unknown workflow [{workflow_id}]")
                    return False
                self._active_workflows[workflow_id] = workflow
                self._active_generations[workflow_id] = workflow.execution_generation
                self._stop_events[workflow_id] = threading.Event()
                self._pause_events[workflow_id] = threading.Event()

            # Active workflows limit check
            active_count = sum(
                1
                for w in self._active_workflows.values()
                if w.status == WorkflowStatus.RUNNING
            )
            ok, msg = self.governor.check_active_workflows_budget(active_count)
            if not ok:
                workflow.status = WorkflowStatus.WAITING_RESOURCE
                logger.warning(f"Workflow [{workflow_id}] deferred: {msg}")
                self.emit_event(workflow_id, "waiting_resource", {"reason": msg})
                return False

            if workflow.status not in (
                WorkflowStatus.READY,
                WorkflowStatus.VALIDATING,
                WorkflowStatus.CREATED,
                WorkflowStatus.RECOVERING,
            ):
                logger.warning(
                    f"Workflow [{workflow_id}] in state {workflow.status} cannot be started."
                )
                return False

            workflow.status = WorkflowStatus.RUNNING
            workflow.started_at = time.time()
            generation = self._active_generations[workflow_id]
            stop_evt = self._stop_events[workflow_id]
            pause_evt = self._pause_events[workflow_id]

        self.db.update_workflow(workflow_id, status=WorkflowStatus.RUNNING.value)
        self.emit_event(workflow_id, "workflow_started", {"generation": generation})

        if run_in_background:
            t = threading.Thread(
                target=self._run_loop,
                args=(workflow_id, generation, stop_evt, pause_evt),
                daemon=True,
                name=f"WorkflowRunner-{workflow_id}",
            )
            with self._orchestrator_lock:
                self._active_threads[workflow_id] = t
            t.start()
            return True
        else:
            self._run_loop(workflow_id, generation, stop_evt, pause_evt)
            return True

    def stop_workflow(
        self, workflow_id: str, reason: str = "User requested stop"
    ) -> bool:
        """Universal STOP: fences generation, cancels running nodes, transitions to STOPPED."""
        if workflow_id in self.stop_events:
            ev = self.stop_events[workflow_id]
            if hasattr(ev, "set"):
                ev.set()
        if workflow_id in self.workflows:
            graph = self.workflows[workflow_id]
            if hasattr(graph, "generation"):
                graph.generation += 1
            if hasattr(graph, "state"):
                graph.state = WorkflowState.CANCELLED
            return True

        with self._orchestrator_lock:
            workflow = self._active_workflows.get(workflow_id)
            if not workflow:
                return False

            new_gen = self._active_generations.get(workflow_id, 1) + 1
            self._active_generations[workflow_id] = new_gen
            workflow.execution_generation = new_gen
            if workflow_id in self._stop_events:
                self._stop_events[workflow_id].set()

            workflow.status = WorkflowStatus.STOPPED
            workflow.completed_at = time.time()

            # Mark all non-terminal nodes as STOPPED
            for n in workflow.nodes:
                if not is_node_terminal(n.status):
                    n.status = WorkflowNodeStatus.STOPPED

        self.db.update_workflow(
            workflow_id,
            status=WorkflowStatus.STOPPED.value,
            execution_generation=new_gen,
        )
        for n in workflow.nodes:
            self.db.update_workflow_node(workflow_id, n.node_id, status=n.status.value)

        self.checkpoint_manager.save_workflow_checkpoint(
            workflow_id=workflow_id,
            task_id=workflow.task_id,
            status=WorkflowStatus.STOPPED.value,
            execution_generation=self._active_generations.get(workflow_id, 1),
            completed_node_ids=[
                n.node_id
                for n in workflow.nodes
                if n.status == WorkflowNodeStatus.COMPLETED
            ],
            failed_node_ids=[
                n.node_id
                for n in workflow.nodes
                if n.status == WorkflowNodeStatus.FAILED
            ],
        )

        self.trace_manager.finalize_workflow_trace(workflow_id, "STOPPED")
        self.emit_event(workflow_id, "workflow_stopped", {"reason": reason})
        logger.info(f"Universal STOP executed on workflow [{workflow_id}]: {reason}")
        return True

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        with self._orchestrator_lock:
            workflow = self._active_workflows.get(workflow_id)
            if not workflow or workflow.status != WorkflowStatus.RUNNING:
                return False

            if workflow_id in self._pause_events:
                self._pause_events[workflow_id].set()

            workflow.status = WorkflowStatus.PAUSED

        self.db.update_workflow(workflow_id, status=WorkflowStatus.PAUSED.value)
        self.emit_event(workflow_id, "workflow_paused", {})
        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow."""
        with self._orchestrator_lock:
            workflow = self._active_workflows.get(workflow_id)
            if not workflow or workflow.status != WorkflowStatus.PAUSED:
                return False

            if workflow_id in self._pause_events:
                self._pause_events[workflow_id].clear()

            workflow.status = WorkflowStatus.RUNNING

        self.db.update_workflow(workflow_id, status=WorkflowStatus.RUNNING.value)
        self.emit_event(workflow_id, "workflow_resumed", {})
        return True

    def recover_workflow(
        self, workflow_id: str
    ) -> tuple[bool, Workflow | None, str | None]:
        """Recover a workflow from its HMAC-authenticated checkpoint after crash."""
        ok, checkpoint, err = self.checkpoint_manager.load_workflow_checkpoint(
            workflow_id
        )
        if not ok or not checkpoint:
            return False, None, f"Failed to load checkpoint: {err}"

        valid, resume_err = self.checkpoint_manager.validate_workflow_for_resume(
            checkpoint
        )
        if not valid:
            return False, None, f"Checkpoint invalid for resume: {resume_err}"

        workflow = self._load_workflow_from_db(workflow_id)
        if not workflow:
            return False, None, f"Workflow [{workflow_id}] not found in database."

        # Increment generation to fence any stale workers
        new_generation = checkpoint.execution_generation + 1
        workflow.execution_generation = new_generation
        workflow.status = WorkflowStatus.RECOVERING

        # Re-apply verified node states from checkpoint
        for node in workflow.nodes:
            if node.node_id in checkpoint.completed_node_ids:
                node.status = WorkflowNodeStatus.COMPLETED
            elif node.node_id in checkpoint.failed_node_ids:
                node.status = WorkflowNodeStatus.FAILED
            elif node.node_id in checkpoint.running_node_ids:
                # Interrupted running node resets to READY for re-execution
                node.status = WorkflowNodeStatus.READY

        with self._orchestrator_lock:
            self._active_workflows[workflow_id] = workflow
            self._active_generations[workflow_id] = new_generation
            self._stop_events[workflow_id] = threading.Event()
            self._pause_events[workflow_id] = threading.Event()

        self.db.update_workflow(
            workflow_id,
            status=WorkflowStatus.RECOVERING.value,
            execution_generation=new_generation,
        )
        self.emit_event(
            workflow_id, "workflow_recovered", {"new_generation": new_generation}
        )

        # Start execution
        self.start_workflow(workflow_id, run_in_background=True)
        return True, workflow, None

    # -----------------------------------------------------------------------
    # Orchestration Run Loop
    # -----------------------------------------------------------------------

    def _run_loop(
        self,
        workflow_id: str,
        generation: int,
        stop_evt: threading.Event,
        pause_evt: threading.Event,
    ) -> None:
        """Main DAG orchestration loop executing on worker thread."""
        logger.info(
            f"Starting orchestration run loop for [{workflow_id}] generation={generation}"
        )

        while True:
            # 1. Generation Fencing Check
            with self._orchestrator_lock:
                current_gen = self._active_generations.get(workflow_id, 1)
                if current_gen != generation:
                    logger.info(
                        f"Run loop fenced: current generation {current_gen} != worker generation {generation}"
                    )
                    return

                workflow = self._active_workflows.get(workflow_id)
                if not workflow or is_workflow_terminal(workflow.status):
                    return

            # 2. Stop Check
            if stop_evt.is_set():
                logger.info(f"Stop signal received in run loop for [{workflow_id}]")
                return

            # 3. Pause Check
            if pause_evt.is_set():
                time.sleep(0.5)
                continue

            # 4. Workflow Duration & Timeout Check
            is_timeout = False
            time_msg = ""
            if workflow.deadline and time.time() > workflow.deadline:
                is_timeout = True
                time_msg = (
                    f"Workflow exceeded absolute deadline of {workflow.deadline}."
                )
            elif workflow.started_at:
                within_time, time_msg = self.governor.check_workflow_duration(
                    workflow.started_at, workflow.resource_budget.max_duration_s
                )
                if not within_time:
                    is_timeout = True

            if is_timeout:
                logger.error(f"Workflow [{workflow_id}] timed out: {time_msg}")
                with self._orchestrator_lock:
                    workflow.status = WorkflowStatus.TIMED_OUT
                self.db.update_workflow(
                    workflow_id, status=WorkflowStatus.TIMED_OUT.value
                )
                self.emit_event(workflow_id, "workflow_timed_out", {"reason": time_msg})
                self.trace_manager.finalize_workflow_trace(workflow_id, "TIMED_OUT")
                return

            # 5. Ready Node Selection
            running_nodes = [
                n for n in workflow.nodes if n.status == WorkflowNodeStatus.RUNNING
            ]
            max_concurrent = min(workflow.resource_budget.max_concurrent_nodes, 2)
            ready_nodes = self.scheduler.get_ready_nodes(
                workflow=workflow,
                max_concurrent=max_concurrent,
                currently_running=len(running_nodes),
            )

            # 6. Terminal & Convergence Checks
            if not ready_nodes and not running_nodes:
                terminal_reason = self.dag_engine.is_workflow_terminal(workflow)
                if terminal_reason == "ALL_COMPLETED":
                    with self._orchestrator_lock:
                        workflow.status = WorkflowStatus.COMPLETED
                        workflow.completed_at = time.time()
                    self.db.update_workflow(
                        workflow_id, status=WorkflowStatus.COMPLETED.value
                    )
                    self.checkpoint_manager.save_workflow_checkpoint(
                        workflow_id=workflow_id,
                        task_id=workflow.task_id,
                        status=WorkflowStatus.COMPLETED.value,
                        execution_generation=generation,
                        completed_node_ids=[
                            n.node_id
                            for n in workflow.nodes
                            if n.status == WorkflowNodeStatus.COMPLETED
                        ],
                    )
                    self.trace_manager.finalize_workflow_trace(workflow_id, "COMPLETED")
                    self.emit_event(workflow_id, "workflow_completed", {})
                    logger.info(f"Workflow [{workflow_id}] completed successfully.")
                    return

                elif terminal_reason == "HAS_FAILURES":
                    # Check if any completed to distinguish PARTIALLY_COMPLETED from FAILED
                    any_completed = any(
                        n.status == WorkflowNodeStatus.COMPLETED for n in workflow.nodes
                    )
                    final_st = (
                        WorkflowStatus.PARTIALLY_COMPLETED
                        if any_completed
                        else WorkflowStatus.FAILED
                    )
                    with self._orchestrator_lock:
                        workflow.status = final_st
                        workflow.completed_at = time.time()
                    self.db.update_workflow(workflow_id, status=final_st.value)
                    self.trace_manager.finalize_workflow_trace(
                        workflow_id, final_st.value
                    )
                    self.emit_event(
                        workflow_id, f"workflow_{final_st.value.lower()}", {}
                    )
                    logger.warning(
                        f"Workflow [{workflow_id}] terminated with status {final_st.value}"
                    )
                    return

                else:
                    # Deadlock or unknown blockage
                    with self._orchestrator_lock:
                        workflow.status = WorkflowStatus.BLOCKED
                    self.db.update_workflow(
                        workflow_id, status=WorkflowStatus.BLOCKED.value
                    )
                    self.emit_event(
                        workflow_id,
                        "workflow_blocked",
                        {"reason": "No ready nodes and unexecuted nodes remain"},
                    )
                    self.trace_manager.finalize_workflow_trace(workflow_id, "BLOCKED")
                    return

            # 7. Execute ready nodes
            for node in ready_nodes:
                if stop_evt.is_set():
                    break

                # Approval gate
                if (
                    node.approval_required
                    and node.status != WorkflowNodeStatus.WAITING_APPROVAL
                ):
                    node.status = WorkflowNodeStatus.WAITING_APPROVAL
                    self.emit_event(
                        workflow_id,
                        "approval_required",
                        {"node_id": node.node_id, "goal": node.goal},
                    )
                    continue

                if node.status == WorkflowNodeStatus.WAITING_APPROVAL:
                    # Waiting for external approval to mark it READY
                    continue

                # Execute node synchronously or spawn
                self._dispatch_node(workflow, node, generation)

            # Polling delay
            time.sleep(0.1)

    def _dispatch_node(
        self, workflow: Workflow, node: WorkflowNode, generation: int
    ) -> None:
        """Execute a single workflow node with locking, retry, and verification."""
        required_locks = self.scheduler.compute_required_locks(node)
        holder_id = f"{workflow.workflow_id}:{node.node_id}"

        # Acquire locks
        acquired = self.lock_manager.acquire_locks(
            required_locks, holder_id, timeout_s=3.0
        )
        if not acquired:
            logger.warning(
                f"Failed to acquire locks for node [{node.node_id}]. Will retry next tick."
            )
            return

        try:
            # Fencing check
            if self._active_generations.get(workflow.workflow_id) != generation:
                return

            node.status = WorkflowNodeStatus.RUNNING
            node.attempt_count += 1
            node.execution_generation = generation
            self.db.update_workflow_node(
                workflow.workflow_id,
                node.node_id,
                status=node.status.value,
                attempt_count=node.attempt_count,
            )
            self.trace_manager.record_node_start(
                workflow.workflow_id, node.node_id, node.goal
            )
            self.emit_event(
                workflow.workflow_id,
                "node_started",
                {
                    "node_id": node.node_id,
                    "goal": node.goal,
                    "attempt": node.attempt_count,
                },
            )

            # Execute action
            success = False
            error_msg = None
            result_data = None

            if self.custom_node_executor:
                success, error_msg, result_data = self.custom_node_executor(node)
            else:
                success, error_msg, result_data = self._default_node_executor(node)

            # Verification
            if success:
                verified, v_err = self._verify_node(node, result_data)
                if not verified:
                    success = False
                    error_msg = f"Node post-action verification failed: {v_err}"

            # Result Handling
            if success:
                node.status = WorkflowNodeStatus.COMPLETED
                node.result = result_data or {}
                self.db.update_workflow_node(
                    workflow.workflow_id, node.node_id, status=node.status.value
                )
                self.trace_manager.record_node_finish(
                    workflow.workflow_id, node.node_id, "COMPLETED", "VERIFIED"
                )
                self.emit_event(
                    workflow.workflow_id,
                    "node_completed",
                    {"node_id": node.node_id, "result": result_data},
                )

                # Checkpoint progress
                self.checkpoint_manager.save_workflow_checkpoint(
                    workflow_id=workflow.workflow_id,
                    task_id=workflow.task_id,
                    status=WorkflowStatus.RUNNING.value,
                    execution_generation=generation,
                    completed_node_ids=[
                        n.node_id
                        for n in workflow.nodes
                        if n.status == WorkflowNodeStatus.COMPLETED
                    ],
                )

            else:
                # Failure & Retry Policy Check
                logger.warning(f"Node [{node.node_id}] execution failed: {error_msg}")
                if (
                    node.attempt_count < node.retry_policy.max_attempts
                    and node.retry_policy.is_retryable(error_msg or "")
                ):
                    node.status = WorkflowNodeStatus.RETRYING
                    self.trace_manager.record_node_finish(
                        workflow.workflow_id,
                        node.node_id,
                        "RETRYING",
                        "FAILED",
                        error_msg,
                    )
                    self.emit_event(
                        workflow.workflow_id,
                        "node_retry",
                        {
                            "node_id": node.node_id,
                            "attempt": node.attempt_count,
                            "max_attempts": node.retry_policy.max_attempts,
                            "error": error_msg,
                        },
                    )
                    backoff = node.retry_policy.get_backoff_seconds(node.attempt_count)
                    time.sleep(min(backoff, 2.0))
                    node.status = WorkflowNodeStatus.READY
                else:
                    node.status = WorkflowNodeStatus.FAILED
                    self.db.update_workflow_node(
                        workflow.workflow_id, node.node_id, status=node.status.value
                    )
                    self.trace_manager.record_node_finish(
                        workflow.workflow_id,
                        node.node_id,
                        "FAILED",
                        "FAILED",
                        error_msg,
                    )
                    self.emit_event(
                        workflow.workflow_id,
                        "node_failed",
                        {"node_id": node.node_id, "error": error_msg},
                    )

                    # Cascade failure to dependent nodes
                    blocked_node_ids = self.dag_engine.cascade_failure(
                        workflow, node.node_id
                    )
                    for blk_id in blocked_node_ids:
                        self.db.update_workflow_node(
                            workflow.workflow_id,
                            blk_id,
                            status=WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY.value,
                        )
                        self.emit_event(
                            workflow.workflow_id,
                            "node_blocked",
                            {
                                "node_id": blk_id,
                                "reason": f"Dependency {node.node_id} failed",
                            },
                        )

        finally:
            self.lock_manager.release_locks(required_locks, holder_id)

    def _default_node_executor(
        self, node: WorkflowNode
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Default node execution handler for system, file, and simulated UI operations."""
        action = node.action or {}
        action_type = action.get("type", "noop").lower()

        # Simulated or lightweight actions
        if action_type in ("noop", "observe", "log"):
            time.sleep(0.05)
            return (
                True,
                None,
                {"output": f"Executed action {action_type} for node {node.node_id}"},
            )

        elif action_type == "read_file":
            path = action.get("path")
            if not path or not os.path.exists(path):
                return False, f"File not found: {path}", None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                return True, None, {"content": content[:1000]}
            except Exception as e:  # noqa: BLE001
                return False, str(e), None

        elif action_type == "write_file":
            path = action.get("path")
            content = action.get("content", "")
            if not path:
                return False, "Missing path for write_file", None
            try:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, None, {"bytes_written": len(content)}
            except Exception as e:  # noqa: BLE001
                return False, str(e), None

        # Generic safe execution fallback
        return True, None, {"action": action_type, "status": "executed"}

    def _verify_node(
        self, node: WorkflowNode, result_data: dict[str, Any] | None
    ) -> tuple[bool, str | None]:
        """Verify node postconditions."""
        for post in node.postconditions:
            cond_type = post.get("type")
            if cond_type == "file_exists":
                f_path = post.get("path")
                if not f_path or not os.path.exists(f_path):
                    return (
                        False,
                        f"Postcondition failed: file '{f_path}' does not exist.",
                    )
            elif cond_type == "output_contains":
                key = post.get("key", "output")
                expected = post.get("expected", "")
                actual = str((result_data or {}).get(key, ""))
                if expected not in actual:
                    return (
                        False,
                        f"Postcondition failed: expected '{expected}' in '{actual}'.",
                    )
        return True, None

    def _load_workflow_from_db(self, workflow_id: str) -> Workflow | None:
        """Reconstruct Workflow from SQLite database."""
        wf_data = self.db.get_workflow(workflow_id)
        if not wf_data:
            return None

        node_rows = self.db.list_workflow_nodes(workflow_id)
        nodes: list[WorkflowNode] = []
        for r in node_rows:
            meta = r.get("metadata") or {}
            raw_priority = meta.get("priority")
            try:
                clamped_priority = (
                    max(1, min(10, int(raw_priority)))
                    if raw_priority is not None
                    else 5
                )
            except (ValueError, TypeError):
                clamped_priority = 5
            raw_risk = str(meta.get("risk_level", "LOW")).upper()
            node = WorkflowNode(
                node_id=r["node_id"],
                workflow_id=r["workflow_id"],
                goal=r["goal"],
                status=WorkflowNodeStatus(r["status"]),
                dependencies=r.get("dependencies", []),
                attempt_count=r.get("attempt_count", 0),
                action=meta.get("action", {}),
                priority=clamped_priority,
                risk_level=raw_risk,
                approval_required=bool(meta.get("approval_required", False)),
                preconditions=meta.get("preconditions", []),
                postconditions=meta.get("postconditions", []),
            )
            nodes.append(node)

        return Workflow(
            workflow_id=wf_data["workflow_id"],
            task_id=wf_data["task_id"],
            goal=wf_data["goal"],
            status=WorkflowStatus(wf_data["status"]),
            nodes=nodes,
            execution_generation=wf_data.get("execution_generation", 1),
            resource_budget=ResourceBudget(**wf_data.get("resource_budget", {})),
            deadline=wf_data.get("deadline"),
            metadata=wf_data.get("metadata", {}),
            created_at=wf_data.get("created_at", time.time()),
            updated_at=wf_data.get("updated_at", time.time()),
        )

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        with self._orchestrator_lock:
            if workflow_id in self._active_workflows:
                return self._active_workflows[workflow_id]
        return self._load_workflow_from_db(workflow_id)

    def list_active_workflows(self) -> list[Workflow]:
        with self._orchestrator_lock:
            return list(self._active_workflows.values())
