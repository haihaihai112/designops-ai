from module3_agent import visual_evaluator


def test_visual_evaluation_requires_image():
    result = visual_evaluator.evaluate_generated_image(None, "侘寂风客厅")

    assert result["status"] == "not_run"
    assert result["overall"] is None


def test_visual_evaluation_parses_and_normalizes_scores():
    result = visual_evaluator._parse_json(
        '{"requirement_match": 92, "spatial_coherence": 85, '
        '"material_fidelity": 101, "lighting_quality": -4, '
        '"issues": ["灯光偏冷"], "evidence": ["可见亚麻沙发"]}'
    )

    assert result["status"] == "completed"
    assert result["material_fidelity"] == 100
    assert result["lighting_quality"] == 0
    assert result["overall"] == 69
