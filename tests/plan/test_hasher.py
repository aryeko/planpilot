"""Tests for plan hasher."""

from __future__ import annotations

from planpilot.models.plan import Epic, Estimate, Plan, Scope, Story, Task, Verification
from planpilot.plan.hasher import compute_plan_id


def create_minimal_plan() -> Plan:
    """Create a minimal valid plan for testing."""
    epic = Epic(
        id="epic1",
        title="Epic",
        goal="Goal",
        spec_ref="spec.md",
        story_ids=["story1"],
        scope=Scope(),
        success_metrics=[],
        risks=[],
        assumptions=[],
    )
    story = Story(
        id="story1",
        epic_id="epic1",
        title="Story",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["task1"],
        scope=Scope(),
        success_metrics=[],
        risks=[],
        assumptions=[],
    )
    task = Task(
        id="task1",
        story_id="story1",
        title="Task",
        motivation="Motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        verification=Verification(),
        artifacts=[],
        depends_on=[],
        estimate=Estimate(),
        scope=Scope(),
    )
    return Plan(epics=[epic], stories=[story], tasks=[task])


def test_compute_plan_id_returns_12_char_hex():
    """Test that compute_plan_id returns a 12-char hex string."""
    plan = create_minimal_plan()
    plan_id = compute_plan_id(plan)

    assert len(plan_id) == 12
    assert all(c in "0123456789abcdef" for c in plan_id)


def test_compute_plan_id_deterministic():
    """Test that the same plan always produces the same hash."""
    plan = create_minimal_plan()
    plan_id1 = compute_plan_id(plan)
    plan_id2 = compute_plan_id(plan)

    assert plan_id1 == plan_id2


def test_compute_plan_id_different_plans_different_hashes():
    """Test that different plans produce different hashes."""
    plan1 = create_minimal_plan()
    plan2 = create_minimal_plan()
    plan2.epics[0].title = "Different Title"

    plan_id1 = compute_plan_id(plan1)
    plan_id2 = compute_plan_id(plan2)

    assert plan_id1 != plan_id2


def test_compute_plan_id_stable_across_reconstruction():
    """Test that separately reconstructed identical plans hash the same."""
    plan1 = create_minimal_plan()
    plan2 = create_minimal_plan()

    plan_id1 = compute_plan_id(plan1)
    plan_id2 = compute_plan_id(plan2)

    assert plan_id1 == plan_id2
