"""Allow running planpilot as ``python -m planpilot``."""

from __future__ import annotations

from planpilot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
