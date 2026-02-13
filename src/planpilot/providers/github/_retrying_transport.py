"""Compatibility shim for retrying transport."""

from planpilot.core.providers.github._retrying_transport import RetryingTransport

__all__ = ["RetryingTransport"]
