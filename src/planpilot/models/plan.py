"""Pydantic models for plan entities: Epic, Story, Task, and Plan.

These models replace the manual JSON validation previously spread across
``sync.py``.  Pydantic handles required-field checks, type coercion, and
default values declaratively.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Scope(BaseModel):
    """In-scope / out-of-scope boundary for an entity."""

    in_scope: list[str] = Field(default_factory=list, alias="in")
    out_scope: list[str] = Field(default_factory=list, alias="out")

    model_config = {"populate_by_name": True}


class SpecRef(BaseModel):
    """Reference to a specification document or section."""

    path: str
    anchor: str = ""
    section: str = ""
    quote: str = ""


class Estimate(BaseModel):
    """Effort estimate attached to a task."""

    tshirt: str = ""
    hours: float | None = None


class Verification(BaseModel):
    """Verification criteria for a task."""

    commands: list[str] = Field(default_factory=list)
    ci_checks: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    manual_steps: list[str] = Field(default_factory=list)


class Epic(BaseModel):
    """Top-level roadmap epic."""

    id: str
    title: str
    goal: str
    spec_ref: SpecRef | str
    story_ids: list[str]
    scope: Scope = Field(default_factory=Scope)
    success_metrics: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Story(BaseModel):
    """User story belonging to an epic."""

    id: str
    epic_id: str
    title: str
    goal: str
    spec_ref: SpecRef | str
    task_ids: list[str]
    scope: Scope = Field(default_factory=Scope)
    success_metrics: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Task(BaseModel):
    """Actionable task belonging to a story."""

    id: str
    story_id: str
    title: str
    motivation: str
    spec_ref: SpecRef | str
    requirements: list[str]
    acceptance_criteria: list[str]
    verification: Verification = Field(default_factory=Verification)
    artifacts: list[str]
    depends_on: list[str]
    estimate: Estimate = Field(default_factory=Estimate)
    scope: Scope = Field(default_factory=Scope)


class Plan(BaseModel):
    """A complete plan consisting of epics, stories, and tasks."""

    epics: list[Epic]
    stories: list[Story]
    tasks: list[Task]
