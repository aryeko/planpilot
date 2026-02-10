"""Rich-based sync progress display."""

from __future__ import annotations

from types import TracebackType
from typing import ClassVar

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.progress import TaskID as RichTaskID

from planpilot.contracts.progress import SyncProgress


class RichSyncProgress(SyncProgress):
    """Live terminal progress bar powered by Rich.

    Use as a context manager so the live display is properly started/stopped::

        with RichSyncProgress() as progress:
            result = await engine.sync(plan, plan_id)
    """

    _PHASE_LABELS: ClassVar[dict[str, str]] = {
        "Discover": "[cyan]Discover[/]",
        "Create": "[green]Create[/]",
        "Enrich": "[blue]Enrich[/]",
        "Relations": "[magenta]Relations[/]",
    }

    def __init__(self) -> None:
        self._console = Console(stderr=True)
        self._progress = Progress(
            SpinnerColumn(finished_text="[green]✓[/green]"),
            TextColumn("{task.description:>14}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self._console,
            transient=False,
        )
        self._task_ids: dict[str, RichTaskID] = {}

    # -- context manager --------------------------------------------------

    def __enter__(self) -> RichSyncProgress:
        self._progress.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._progress.stop()

    # -- SyncProgress implementation --------------------------------------

    def phase_start(self, phase: str, total: int | None = None) -> None:
        label = self._PHASE_LABELS.get(phase, phase)
        if total is not None:
            task_id = self._progress.add_task(label, total=total)
        else:
            # Indeterminate phase (e.g. Discover) — pulsing bar, no counter.
            task_id = self._progress.add_task(label, total=None)
        self._task_ids[phase] = task_id

    def item_done(self, phase: str) -> None:
        task_id = self._task_ids.get(phase)
        if task_id is not None:
            self._progress.advance(task_id)

    def phase_done(self, phase: str) -> None:
        task_id = self._task_ids.get(phase)
        if task_id is None:
            return
        task = self._progress.tasks[task_id]
        if task.total is not None:
            self._progress.update(task_id, completed=task.total)
        else:
            # Indeterminate phase — mark finished by setting total = completed.
            self._progress.update(task_id, total=1, completed=1)
