from module6_observability import tracing


def test_disabled_observability_is_noop():
    status = tracing.initialize_observability(
        {
            "enabled": False,
            "project_name": "test-project",
            "endpoint": "http://localhost:6006/v1/traces",
        },
        force=True,
    )

    assert status["enabled"] is False
    assert status["active"] is False
    with tracing.trace_span("test") as span:
        assert span is None
