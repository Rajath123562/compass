"""
COMPASS Phase 6 — Step Dependency Manager
Enforces strict Directed Acyclic Graph (DAG) validation, topological sorting,
ready-step calculation, and cascading blocks across multi-step execution graphs.
"""

from __future__ import annotations

from collections import defaultdict, deque

from backend.app.logging_config import logger
from planner.models import DecomposedPlan, StepStatus, TaskStep


class DependencyValidationError(ValueError):
    """Raised when a dependency graph contains cycles, missing references, or invalid nodes."""



class StepDependencyManager:
    """
    Validates and manages dependencies between TaskSteps in a DecomposedPlan.
    Guarantees deterministic execution order and prevents downstream action on unverified prerequisites.
    """

    def __init__(self, plan: DecomposedPlan | None = None):
        self.plan = plan

    def validate_dag(self, steps: list[TaskStep]) -> tuple[bool, str | None]:
        """
        Verify that steps form a valid, non-empty, cycle-free Directed Acyclic Graph (DAG).
        Returns (is_valid, error_message).
        """
        if not steps:
            return False, "Plan contains zero steps."

        step_ids = set()
        for step in steps:
            if not step.step_id or not step.step_id.strip():
                return False, "Step found with missing or blank step_id."
            if step.step_id in step_ids:
                return False, f"Duplicate step_id detected: '{step.step_id}'."
            step_ids.add(step.step_id)

        # Adjacency list and in-degree tracking
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {sid: 0 for sid in step_ids}

        for step in steps:
            for dep in step.dependencies:
                # 1. Missing dependency reference
                if dep not in step_ids:
                    return (
                        False,
                        f"Step '{step.step_id}' references non-existent dependency '{dep}'.",
                    )
                # 2. Self-dependency
                if dep == step.step_id:
                    return False, f"Step '{step.step_id}' cannot depend on itself."

                # Edge: dep -> step.step_id (dep must execute before step)
                adj[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        # Cycle Detection via Kahn's Algorithm
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(step_ids):
            # Find cycle participants
            cycle_nodes = [sid for sid, deg in in_degree.items() if deg > 0]
            return (
                False,
                f"Circular dependency detected involving steps: {cycle_nodes}.",
            )

        return True, None

    def get_topological_order(self, steps: list[TaskStep]) -> list[TaskStep]:
        """
        Return steps in a valid, deterministic topological execution order.
        Raises DependencyValidationError if a cycle is detected.
        """
        is_valid, err = self.validate_dag(steps)
        if not is_valid:
            raise DependencyValidationError(err)

        step_map = {s.step_id: s for s in steps}
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {s.step_id: 0 for s in steps}

        for s in steps:
            for dep in s.dependencies:
                adj[dep].append(s.step_id)
                in_degree[s.step_id] += 1

        # Deterministic sorting for tie-breaking
        queue = deque(sorted([sid for sid, deg in in_degree.items() if deg == 0]))
        ordered: list[TaskStep] = []

        while queue:
            curr_id = queue.popleft()
            ordered.append(step_map[curr_id])
            for nbr in sorted(adj[curr_id]):
                in_degree[nbr] -= 1
                if in_degree[nbr] == 0:
                    queue.append(nbr)

        return ordered

    def get_ready_steps(self, steps: list[TaskStep]) -> list[TaskStep]:
        """
        Compute which steps are currently READY to execute:
        A step is READY if:
        1. status is PENDING
        2. All prerequisite steps (dependencies) have status == COMPLETED
        """
        completed_ids = {s.step_id for s in steps if s.status == StepStatus.COMPLETED}
        ready: list[TaskStep] = []

        for s in steps:
            if s.status != StepStatus.PENDING:
                continue
            all_deps_met = all(dep in completed_ids for dep in s.dependencies)
            if all_deps_met:
                ready.append(s)

        return ready

    def cascade_downstream_blocks(self, steps: list[TaskStep]) -> list[TaskStep]:
        """
        If any step is FAILED, UNVERIFIED, or BLOCKED, all downstream dependent steps
        that require it must be transitioned to BLOCKED.
        Returns the updated list of steps.
        """
        # Step IDs that failed or are blocked
        compromised_ids: set[str] = {
            s.step_id
            for s in steps
            if s.status
            in [StepStatus.FAILED, StepStatus.UNVERIFIED, StepStatus.BLOCKED]
        }

        # Build forward adjacency: prerequisite -> list of dependents
        forward_adj: dict[str, list[str]] = defaultdict(list)
        for s in steps:
            for dep in s.dependencies:
                forward_adj[dep].append(s.step_id)

        # BFS to find all downstream steps
        blocked_downstream: set[str] = set()
        queue = deque(list(compromised_ids))

        while queue:
            curr = queue.popleft()
            for dep_step_id in forward_adj[curr]:
                if (
                    dep_step_id not in blocked_downstream
                    and dep_step_id not in compromised_ids
                ):
                    blocked_downstream.add(dep_step_id)
                    queue.append(dep_step_id)

        # Apply blocks
        for s in steps:
            if s.step_id in blocked_downstream and s.status == StepStatus.PENDING:
                s.status = StepStatus.BLOCKED
                s.error = "Blocked: upstream prerequisite dependency was not successfully completed."
                logger.warning(
                    f"Step [{s.step_id}] cascaded to BLOCKED due to upstream failure."
                )

        return steps
