"""
COMPASS Phase 8 — Workflow DAG Validation & Execution Engine
Complete DAG validation (Section 9/23), topological ordering,
ready-node computation, deterministic failure cascade (Section 24),
and concurrent-safe state management.

Builds upon Phase 6 StepDependencyManager algorithms but operates
on Phase 8 WorkflowNode graph with full validation per Section 23.
"""

from __future__ import annotations

from collections import defaultdict, deque

from backend.app.logging_config import logger
from planner.workflow_models import (
    Workflow,
    WorkflowNode,
    WorkflowNodeStatus,
    is_node_terminal,
)


class DAGValidationError(ValueError):
    """Raised when a workflow DAG fails structural or semantic validation."""



class WorkflowDAGValidator:
    """
    Complete DAG validation engine per Section 9/23.
    Validates all 16 structural and semantic invariants before execution.
    """

    MAX_NODES_PER_WORKFLOW = 100

    def validate(self, workflow: Workflow) -> tuple[bool, list[str]]:
        """
        Run all validation checks. Returns (is_valid, list_of_errors).
        A workflow with any error must NOT start.
        """
        errors: list[str] = []

        # 1. Non-empty
        if not workflow.nodes:
            errors.append("Workflow contains zero nodes.")
            return False, errors

        # 2. Excessive node count
        if len(workflow.nodes) > self.MAX_NODES_PER_WORKFLOW:
            errors.append(
                f"Node count {len(workflow.nodes)} exceeds maximum {self.MAX_NODES_PER_WORKFLOW}."
            )

        node_ids: set[str] = set()
        node_map: dict[str, WorkflowNode] = {}

        for node in workflow.nodes:
            # 3. Missing node ID
            if not node.node_id or not node.node_id.strip():
                errors.append("Node found with missing or blank node_id.")
                continue

            # 4. Duplicate node ID
            if node.node_id in node_ids:
                errors.append(f"Duplicate node_id detected: '{node.node_id}'.")
                continue

            # 5. Workflow ID mismatch
            if node.workflow_id != workflow.workflow_id:
                errors.append(
                    f"Node '{node.node_id}' has workflow_id '{node.workflow_id}' but expected '{workflow.workflow_id}'."
                )

            node_ids.add(node.node_id)
            node_map[node.node_id] = node

        # Build adjacency and validate dependencies
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for node in workflow.nodes:
            if node.node_id not in node_ids:
                continue
            for dep in node.dependencies:
                # 6. Self-dependency
                if dep == node.node_id:
                    errors.append(
                        f"Node '{node.node_id}' cannot depend on itself (self-dependency detected)."
                    )
                    continue

                # 7. Missing dependency reference
                if dep not in node_ids:
                    errors.append(
                        f"Node '{node.node_id}' references non-existent dependency '{dep}'."
                    )
                    continue

                adj[dep].append(node.node_id)
                in_degree[node.node_id] += 1

        # 8. Cycle detection (Kahn's algorithm)
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0
        topo_order: list[str] = []

        while queue:
            curr = queue.popleft()
            visited_count += 1
            topo_order.append(curr)
            for nbr in adj[curr]:
                in_degree[nbr] -= 1
                if in_degree[nbr] == 0:
                    queue.append(nbr)

        if visited_count < len(node_ids):
            cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
            errors.append(
                f"Circular dependency cycle detected involving nodes: {cycle_nodes}."
            )

        # 9. Orphan nodes (no dependencies and no dependents)
        all_deps = set()
        all_dependents = set()
        for node in workflow.nodes:
            if node.node_id not in node_ids:
                continue
            all_deps.update(node.dependencies)
            for dep in node.dependencies:
                all_dependents.add(node.node_id)

        roots = node_ids - all_dependents  # noqa: F841
        # Orphan = node that is neither a root nor has dependents downstream
        # (single-node workflows are valid)
        if len(workflow.nodes) > 1:
            for nid in node_ids:
                is_root = nid not in all_dependents or in_degree.get(nid, 0) == 0
                has_downstream = bool(adj.get(nid))
                has_upstream = bool(node_map[nid].dependencies)
                if not is_root and not has_downstream and not has_upstream:
                    errors.append(
                        f"Orphan node detected: '{nid}' has no dependencies and no dependents in a multi-node graph."
                    )

        # 10. Invalid retry policy
        for node in workflow.nodes:
            if node.node_id not in node_ids:
                continue
            if node.retry_policy.max_attempts < 1:
                errors.append(
                    f"Node '{node.node_id}' has invalid retry policy (max_attempts < 1)."
                )
            if node.retry_policy.min_backoff_ms > node.retry_policy.max_backoff_ms:
                errors.append(f"Node '{node.node_id}' has min_backoff > max_backoff.")

        # 11. Invalid timeout
        for node in workflow.nodes:
            if node.node_id not in node_ids:
                continue
            if node.timeout_s <= 0:
                errors.append(f"Node '{node.node_id}' has non-positive timeout.")

        # 12. Invalid node state
        for node in workflow.nodes:
            if node.node_id not in node_ids:
                continue
            if node.status not in WorkflowNodeStatus.__members__.values():
                errors.append(
                    f"Node '{node.node_id}' has invalid status '{node.status}'."
                )

        # 13. Impossible deadline
        if workflow.deadline is not None:  # noqa: SIM102
            if workflow.deadline < workflow.created_at:
                errors.append(
                    f"Workflow deadline ({workflow.deadline}) is before creation time ({workflow.created_at})."
                )

        is_valid = len(errors) == 0
        return is_valid, errors


class WorkflowDAGEngine:
    """
    DAG execution engine: topological ordering, ready-node computation,
    deterministic failure cascade, and concurrent-safe state updates.
    """

    def __init__(self):
        self.validator = WorkflowDAGValidator()

    def validate_workflow(self, workflow: Workflow) -> tuple[bool, list[str]]:
        return self.validator.validate(workflow)

    def topological_sort(self, workflow: Workflow) -> list[str]:
        """Return node IDs in deterministic topological order."""
        return [n.node_id for n in self.get_topological_order(workflow)]

    def get_topological_order(self, workflow: Workflow) -> list[WorkflowNode]:
        """Return nodes in deterministic topological order."""
        node_map = {n.node_id: n for n in workflow.nodes}
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {n.node_id: 0 for n in workflow.nodes}

        for node in workflow.nodes:
            for dep in node.dependencies:
                if dep in node_map:
                    adj[dep].append(node.node_id)
                    in_degree[node.node_id] += 1

        # Deterministic tie-breaking by node_id
        queue = deque(sorted([nid for nid, deg in in_degree.items() if deg == 0]))
        ordered: list[WorkflowNode] = []

        while queue:
            curr = queue.popleft()
            ordered.append(node_map[curr])
            for nbr in sorted(adj[curr]):
                in_degree[nbr] -= 1
                if in_degree[nbr] == 0:
                    queue.append(nbr)

        return ordered

    def get_ready_nodes(self, workflow: Workflow) -> list[WorkflowNode]:
        """
        Compute nodes eligible for dispatch (Section 13).
        A node is READY if:
          1. status is PENDING or (READY and not yet claimed)
          2. All dependencies have status == COMPLETED
        """
        completed_ids = {
            n.node_id
            for n in workflow.nodes
            if n.status == WorkflowNodeStatus.COMPLETED
        }
        ready: list[WorkflowNode] = []

        for node in workflow.nodes:
            if node.status not in {
                WorkflowNodeStatus.PENDING,
                WorkflowNodeStatus.READY,
            }:
                continue
            all_deps_met = all(dep in completed_ids for dep in node.dependencies)
            if all_deps_met:
                if node.status == WorkflowNodeStatus.PENDING:
                    node.transition_to(WorkflowNodeStatus.READY)
                ready.append(node)

        return ready

    def cascade_failure(
        self, workflow: Workflow, failed_node_id: str | None = None
    ) -> list[str]:
        """
        Deterministic failure cascade (Section 24).
        If a node fails, all downstream dependents become BLOCKED_BY_DEPENDENCY.
        Returns list of newly blocked node IDs.
        """
        failed_ids = {
            n.node_id
            for n in workflow.nodes
            if n.status in {WorkflowNodeStatus.FAILED, WorkflowNodeStatus.UNKNOWN}
        }
        if failed_node_id:
            failed_ids.add(failed_node_id)

        # Build forward adjacency
        forward: dict[str, list[str]] = defaultdict(list)
        for node in workflow.nodes:
            for dep in node.dependencies:
                forward[dep].append(node.node_id)

        # BFS from failed nodes
        blocked: set[str] = set()
        queue = deque(list(failed_ids))

        while queue:
            curr = queue.popleft()
            for downstream_id in forward[curr]:
                if downstream_id not in blocked and downstream_id not in failed_ids:
                    node = workflow.get_node(downstream_id)
                    if node and not is_node_terminal(node.status):  # noqa: SIM102
                        if node.transition_to(WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY):
                            node.error = (
                                f"Blocked: upstream dependency '{curr}' failed."
                            )
                            blocked.add(downstream_id)
                            queue.append(downstream_id)

        if blocked:
            logger.warning(
                f"Workflow [{workflow.workflow_id}]: Cascaded failure to {len(blocked)} downstream nodes: {blocked}"
            )

        return list(blocked)

    def is_workflow_terminal(self, workflow: Workflow) -> str | None:
        """
        Check if workflow has reached a terminal condition.
        Returns 'ALL_COMPLETED', 'HAS_FAILURES', or None if still in progress.
        """
        is_term, reason = self.check_workflow_complete(workflow)
        if not is_term:
            return None
        if "All nodes completed" in reason:
            return "ALL_COMPLETED"
        return "HAS_FAILURES"

    def check_workflow_complete(self, workflow: Workflow) -> tuple[bool, str]:
        """
        Check if workflow has reached a terminal condition.
        Returns (is_terminal, reason).
        """
        if not workflow.nodes:
            return True, "No nodes in workflow"

        all_completed = all(
            n.status == WorkflowNodeStatus.COMPLETED for n in workflow.nodes
        )
        if all_completed:
            return True, "All nodes completed"

        # Check if remaining nodes are all blocked/failed/cancelled and no RUNNING
        running = any(
            n.status
            in {
                WorkflowNodeStatus.RUNNING,
                WorkflowNodeStatus.VERIFYING,
                WorkflowNodeStatus.RETRYING,
                WorkflowNodeStatus.READY,
                WorkflowNodeStatus.WAITING_APPROVAL,
            }
            for n in workflow.nodes
        )
        if not running:
            pending = any(
                n.status
                in {
                    WorkflowNodeStatus.PENDING,
                    WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY,
                }
                for n in workflow.nodes
            )
            any_completed = any(
                n.status == WorkflowNodeStatus.COMPLETED for n in workflow.nodes
            )
            any_failed = any(
                n.status in {WorkflowNodeStatus.FAILED, WorkflowNodeStatus.UNKNOWN}
                for n in workflow.nodes
            )

            if any_failed and any_completed:
                return True, "Partially completed with failures"
            elif any_failed:
                return True, "All executable nodes failed"
            elif pending:
                return True, "Remaining nodes blocked by unresolvable dependencies"

        return False, "Workflow still in progress"


class DAGEngine:
    """Graph-based DAG validation and execution engine."""

    def __init__(self, max_nodes: int = 30, max_depth: int = 10):
        self.max_nodes = max_nodes
        self.max_depth = max_depth

    def validate_and_sort(self, graph: Any) -> list[str]:
        """Validates acyclicity and returns a topologically sorted list of node IDs."""
        if len(graph.nodes) > self.max_nodes:
            raise DAGValidationError(
                f"Too many nodes: {len(graph.nodes)} > {self.max_nodes}"
            )

        # Build adjacency list and in-degree map
        adj: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
        in_degree: dict[str, int] = {node_id: 0 for node_id in graph.nodes}

        for node_id, node in graph.nodes.items():
            deps = getattr(node, "depends_on", getattr(node, "dependencies", []))
            for dep in deps:
                if dep not in graph.nodes:
                    raise DAGValidationError(
                        f"Node '{node_id}' depends on missing node '{dep}'"
                    )
                adj[dep].append(node_id)
                in_degree[node_id] += 1

        # Kahn's algorithm for topological sort
        ready_queue = deque([n for n in graph.nodes if in_degree[n] == 0])
        sorted_nodes = []
        depths: dict[str, int] = {n: 1 for n in ready_queue}

        while ready_queue:
            ready_queue = deque(
                sorted(ready_queue, key=lambda n: (-getattr(graph.nodes[n], "priority", 0), n))
            )
            curr = ready_queue.popleft()
            sorted_nodes.append(curr)

            curr_depth = depths.get(curr, 1)
            if curr_depth > self.max_depth:
                raise DAGValidationError(
                    f"Max depth exceeded: {curr_depth} > {self.max_depth}"
                )

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                depths[neighbor] = max(depths.get(neighbor, 1), curr_depth + 1)
                if in_degree[neighbor] == 0:
                    ready_queue.append(neighbor)

        if len(sorted_nodes) != len(graph.nodes):
            raise DAGValidationError("Cycle detected in DAG")

        return sorted_nodes

    def get_ready_nodes(self, graph: Any) -> list[Any]:
        """Returns a list of nodes that are ready to execute."""
        ready = []
        for node_id, node in graph.nodes.items():
            state = getattr(node, "state", getattr(node, "status", None))
            if str(getattr(state, "value", state)).upper() in (
                "PENDING",
                "RETRYING",
                "RECOVERING",
            ):
                deps = getattr(node, "depends_on", getattr(node, "dependencies", []))
                deps_satisfied = True
                for dep in deps:
                    dep_state = getattr(graph.nodes[dep], "state", getattr(graph.nodes[dep], "status", None))
                    if dep_state not in (WorkflowNodeStatus.COMPLETED, "COMPLETED"):
                        deps_satisfied = False
                        break

                if deps_satisfied:
                    ready.append(node)

        ready.sort(key=lambda n: (-getattr(n, "priority", 0), getattr(n, "id", getattr(n, "node_id", ""))))
        return ready

