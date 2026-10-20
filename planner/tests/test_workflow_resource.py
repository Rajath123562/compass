"""
Tests for Phase 8 Workflow Resource Bounds and Governance (Gate 18).
"""

from planner.resource_governor import (
    MAX_ACTIVE_WORKFLOWS,
    MAX_CONCURRENT_NODES,
    MAX_NODES_PER_WORKFLOW,
    ResourceGovernor,
)


def test_resource_governor_node_budget():
    governor = ResourceGovernor()
    ok, _ = governor.check_workflow_node_budget(10)
    assert ok

    ok_max, _ = governor.check_workflow_node_budget(MAX_NODES_PER_WORKFLOW)
    assert ok_max

    exceeded, msg = governor.check_workflow_node_budget(MAX_NODES_PER_WORKFLOW + 1)
    assert not exceeded
    assert "exceeds maximum" in msg


def test_resource_governor_active_workflows():
    governor = ResourceGovernor()
    ok, _ = governor.check_active_workflows_budget(2)
    assert ok

    exceeded, msg = governor.check_active_workflows_budget(MAX_ACTIVE_WORKFLOWS)
    assert not exceeded
    assert "reached maximum" in msg


def test_resource_governor_concurrent_nodes():
    governor = ResourceGovernor()
    ok, _ = governor.check_concurrent_nodes_budget(1)
    assert ok

    exceeded, msg = governor.check_concurrent_nodes_budget(MAX_CONCURRENT_NODES)
    assert not exceeded
    assert "reached maximum" in msg


def test_resource_governor_measured_snapshot():
    governor = ResourceGovernor()
    snap = governor.measure_resources()
    assert snap.compass_backend_rss_mb > 0
    assert snap.system_ram_total_mb > 0
    assert snap.screenshot_buffer_count >= 0
