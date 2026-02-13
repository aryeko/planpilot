from __future__ import annotations

from planpilot.core.contracts.init import InitProgress


def test_init_progress_protocol_methods_are_callable() -> None:
    target = object()

    InitProgress.phase_start(target, "phase", 1)
    InitProgress.phase_done(target, "phase")
    InitProgress.phase_error(target, "phase", RuntimeError("boom"))
