"""Optional Phoenix/OpenTelemetry integration for InteriorForge AI."""

from module6_observability.tracing import initialize_observability, trace_span

__all__ = ["initialize_observability", "trace_span"]
