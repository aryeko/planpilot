"""Progress reporting protocol for the sync pipeline.

This is engine-level instrumentation — not a provider contract.
The engine emits phase lifecycle events; consumers (e.g. the CLI's Rich
progress bar) implement ``SyncProgress`` to render feedback.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SyncProgress(ABC):
    """Observer interface for sync pipeline progress events.

    Implementations receive phase-level lifecycle callbacks
    so they can drive progress bars, logs, or any other feedback.
    """

    @abstractmethod
    def phase_start(self, phase: str, total: int | None = None) -> None:
        """A sync phase is starting. *total* is ``None`` for indeterminate phases."""
        ...  # pragma: no cover

    @abstractmethod
    def item_done(self, phase: str) -> None:
        """One item within *phase* has completed."""
        ...  # pragma: no cover

    @abstractmethod
    def phase_done(self, phase: str) -> None:
        """The *phase* has finished successfully."""
        ...  # pragma: no cover

    @abstractmethod
    def phase_error(self, phase: str, error: BaseException) -> None:
        """The *phase* was interrupted by *error*."""
        ...  # pragma: no cover


class NullSyncProgress(SyncProgress):
    """No-op implementation used when no progress display is requested."""

    def phase_start(self, phase: str, total: int | None = None) -> None:
        pass

    def item_done(self, phase: str) -> None:
        pass

    def phase_done(self, phase: str) -> None:
        pass

    def phase_error(self, phase: str, error: BaseException) -> None:
        pass
