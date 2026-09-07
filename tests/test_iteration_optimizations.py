from module2_rag.query_knowledge import rerank_results
from module3_agent.agent_pipeline import _repair_prompt_coverage
from module3_agent.quality_evaluator import evaluate_design_bundle
from module3_agent import openai_image_client
from module3_agent.requirement_parser import parse_design_requirement


def test_rag_rerank_prefers_relevance_and_source_diversity():
    results = [
        {"text": "侘寂风客厅使用亚麻和原木，保持自然光", "source": "wabi.md", "distance": 0.1},
        {"text": "侘寂风客厅使用亚麻和原木，保持自然光，补充收纳", "source": "wabi.md", "distance": 0.08},
        {"text": "落地窗引入自然光，客厅采用低饱和色彩", "source": "lighting.md", "distance": 0.2},
    ]

    reranked = rerank_results("侘寂风客厅落地窗", results, top_k=2)

    assert reranked[0]["source"] == "wabi.md"
    assert reranked[1]["source"] == "lighting.md"


def test_prompt_repair_adds_missing_hard_constraints():
    parsed = parse_design_requirement("20平米侘寂风客厅，需要亚麻沙发、落地窗和暖光")

    repaired, missing = _repair_prompt_coverage("wabi-sabi living room, interior render", parsed)

    assert set(missing) == {"亚麻", "沙发", "落地窗", "暖光"}
    assert "linen" in repaired
    assert "sofa" in repaired
    assert "floor-to-ceiling window" in repaired
    assert "warm light" in repaired


def test_quality_style_aliases_match_hyphenated_prompt():
    parsed = parse_design_requirement("侘寂风客厅")
    quality = evaluate_design_bundle(parsed, {"positive_prompt": "wabi-sabi living room"})

    assert quality["intent_alignment"] == 100


def test_openai_image_client_requires_key(monkeypatch):
    monkeypatch.setitem(openai_image_client.IMAGE_CONFIG, "api_key", "")

    result = openai_image_client.generate_openai_image("a calm living room")

    assert result["success"] is False
    assert result["provider"] == "openai"
    assert "OPENAI_API_KEY" in result["error"]
