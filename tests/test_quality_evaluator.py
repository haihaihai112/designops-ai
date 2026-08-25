from module3_agent.quality_evaluator import evaluate_design_bundle
from module3_agent.requirement_parser import parse_design_requirement


def test_quality_score_recognizes_english_prompt_aliases():
    parsed = parse_design_requirement("20平米侘寂风客厅，亚麻沙发、原木茶几和落地窗")
    result = {
        "positive_prompt": (
            "wabisabi living room, linen sofa, solid wood coffee table, floor-to-ceiling window, "
            "natural material, soft lighting, wide angle interior render, photorealistic"
        ),
        "analysis": "完整分析",
        "coohom_brief": "完整 brief",
        "asset_tags": "完整标签",
        "social_copy": "完整发布包",
    }

    quality = evaluate_design_bundle(parsed, result)

    assert quality["requirement_coverage"] == 100
    assert quality["intent_alignment"] == 100
    assert quality["deliverable_completeness"] == 100
    assert quality["overall"] >= 85


def test_quality_score_reports_missing_deliverables():
    parsed = parse_design_requirement("极简客厅")
    quality = evaluate_design_bundle(parsed, {"positive_prompt": "minimalist living room"})

    assert quality["deliverable_completeness"] == 0
    assert "部分运营交付物缺失" in quality["notes"]

