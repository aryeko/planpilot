"""Enumerated types used across planpilot."""

from __future__ import annotations

from enum import StrEnum


class EntityType(StrEnum):
    """Discriminator for the three plan entity kinds."""

    EPIC = "epic"
    STORY = "story"
    TASK = "task"
