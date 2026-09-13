import json

from module3_agent import tool_agent


def test_parse_design_brief_tool_returns_json():
    result = json.loads(tool_agent.parse_design_brief("18平米侘寂风客厅，亚麻沙发"))

    assert result["area_sqm"] == 18
    assert result["style_code"] == "wabisabi"
    assert "亚麻" in result["keywords"]


def test_search_tool_returns_compact_citations(monkeypatch):
    monkeypatch.setattr(
        tool_agent,
        "query_design_knowledge",
        lambda query, top_k: [
            {"text": "亚麻和原木适合侘寂风。", "source": "wabi.md", "distance": 0.1}
        ],
    )

    result = json.loads(tool_agent.search_design_knowledge("侘寂风材质"))

    assert result[0]["source"] == "wabi.md"
    assert "亚麻" in result[0]["excerpt"]
