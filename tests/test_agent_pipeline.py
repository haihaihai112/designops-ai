from module3_agent import agent_pipeline


def test_placeholder_api_key_does_not_enable_remote_llm(monkeypatch):
    monkeypatch.setitem(agent_pipeline.LLM_CONFIG, "api_base", "https://api.deepseek.com/v1")
    monkeypatch.setitem(agent_pipeline.LLM_CONFIG, "api_key", "your-api-key")

    assert agent_pipeline._should_use_llm() is False


def test_agent_fallback_contract(monkeypatch):
    monkeypatch.setattr(agent_pipeline, "_should_use_llm", lambda: False)
    monkeypatch.setattr(
        agent_pipeline,
        "_query_rag_bundle",
        lambda user_input, style: {
            "context": "mock knowledge",
            "citations": [{"index": 1, "source": "wabi_sabi.md", "excerpt": "自然材质", "distance": 0.2}],
            "warning": "",
        },
    )

    result = agent_pipeline.run_agent("20平米侘寂风客厅，亚麻沙发", generate=False, variant="practical")

    assert result["generation_mode"] == "fallback"
    assert result["variant"] == "practical"
    assert result["structured_requirement"]["area_sqm"] == 20
    assert result["rag_citations"][0]["source"] == "wabi_sabi.md"
    assert "buildable layout" in result["positive_prompt"]
    assert result["quality"]["overall"] > 0
    assert result["timings"]["image"] == 0
    assert result["timings"]["total"] >= 0
    assert result["llm_backend"] in {"openai", "litellm"}
    assert result["observability"]["active"] is False

