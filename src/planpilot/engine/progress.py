"""Compatibility shim for sync progress protocol."""

from planpilot.core.engine.progress import NullSyncProgress, SyncProgress

__all__ = ["NullSyncProgress", "SyncProgress"]
