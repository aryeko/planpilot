"""Tests for RichSyncProgress and NullSyncProgress."""

from __future__ import annotations

from planpilot.contracts.progress import NullSyncProgress, SyncProgress
from planpilot.progress import RichSyncProgress


class TestNullSyncProgress:
    """NullSyncProgress is a no-op implementation."""

    def test_implements_protocol(self) -> None:
        assert issubclass(NullSyncProgress, SyncProgress)

    def test_phase_lifecycle_is_noop(self) -> None:
        progress = NullSyncProgress()
        # Should not raise
        progress.phase_start("Discover", total=5)
        progress.item_done("Discover")
        progress.phase_done("Discover")


class TestRichSyncProgress:
    """RichSyncProgress drives Rich progress bars."""

    def test_implements_protocol(self) -> None:
        assert issubclass(RichSyncProgress, SyncProgress)

    def test_context_manager(self) -> None:
        progress = RichSyncProgress()
        with progress as p:
            assert p is progress

    def test_determinate_phase(self) -> None:
        with RichSyncProgress() as progress:
            progress.phase_start("Create", total=3)
            progress.item_done("Create")
            progress.item_done("Create")
            progress.item_done("Create")
            progress.phase_done("Create")

    def test_indeterminate_phase(self) -> None:
        with RichSyncProgress() as progress:
            progress.phase_start("Discover", total=None)
            progress.item_done("Discover")
            progress.phase_done("Discover")

    def test_phase_done_with_unknown_phase_is_noop(self) -> None:
        with RichSyncProgress() as progress:
            # Should not raise even when phase was never started.
            progress.phase_done("Unknown")

    def test_item_done_with_unknown_phase_is_noop(self) -> None:
        with RichSyncProgress() as progress:
            # Should not raise even when phase was never started.
            progress.item_done("Unknown")

    def test_multiple_phases_sequentially(self) -> None:
        with RichSyncProgress() as progress:
            for phase, total in [("Discover", None), ("Create", 5), ("Enrich", 5), ("Relations", 4)]:
                progress.phase_start(phase, total=total)
                if total:
                    for _ in range(total):
                        progress.item_done(phase)
                progress.phase_done(phase)
