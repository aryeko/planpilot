"""Contracts for init preflight workflows."""

from __future__ import annotations

from typing import Protocol


class InitProgress(Protocol):
    def phase_start(self, phase: str, total: int | None = None) -> None: ...

    def phase_done(self, phase: str) -> None: ...

    def phase_error(self, phase: str, error: BaseException) -> None: ...
