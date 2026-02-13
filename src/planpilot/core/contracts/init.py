"""Contracts for init preflight workflows."""

from __future__ import annotations

from typing import Protocol


class InitProgress(Protocol):
    def phase_start(self, phase: str, total: int | None = None) -> None:
        pass

    def phase_done(self, phase: str) -> None:
        pass

    def phase_error(self, phase: str, error: BaseException) -> None:
        pass
