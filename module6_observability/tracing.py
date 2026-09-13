"""Lazy Phoenix tracing that leaves the core application dependency-free."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, Iterator

from config import OBSERVABILITY_CONFIG

_initialized = False
_status: dict[str, Any] = {"enabled": False, "active": False, "warning": ""}
_tracer = None


def initialize_observability(
    config: Mapping[str, Any] | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Initialize Phoenix once and return a serializable runtime status."""
    global _initialized, _status, _tracer

    if _initialized and not force:
        return dict(_status)

    settings = dict(OBSERVABILITY_CONFIG if config is None else config)
    enabled = bool(settings.get("enabled", False))
    _initialized = True
    _tracer = None
    _status = {
        "enabled": enabled,
        "active": False,
        "project_name": settings.get("project_name", "interiorforge-ai"),
        "endpoint": settings.get("endpoint", ""),
        "warning": "",
    }
    if not enabled:
        return dict(_status)

    try:
        from phoenix.otel import register

        tracer_provider = register(
            project_name=_status["project_name"],
            endpoint=_status["endpoint"],
            auto_instrument=True,
        )
        _tracer = tracer_provider.get_tracer("interiorforge-ai")
        _status["active"] = True
    except Exception as exc:
        _status["warning"] = f"Phoenix 初始化失败，已继续无追踪运行：{exc}"
    return dict(_status)


@contextmanager
def trace_span(name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Any]:
    """Create a manual child span when Phoenix is active."""
    if _tracer is None:
        yield None
        return

    clean_attributes = {
        key: value
        for key, value in (attributes or {}).items()
        if isinstance(value, (str, bool, int, float))
    }
    with _tracer.start_as_current_span(name, attributes=clean_attributes) as span:
        yield span
