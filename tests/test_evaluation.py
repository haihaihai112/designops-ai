from module5_ops.evaluation import _case_metrics, load_cases, write_report


def test_fixed_evaluation_cases_are_valid():
    cases = load_cases()

    assert len(cases) >= 5
    assert all(case.get("id") and case.get("requirement") for case in cases)


def test_case_metrics_and_report(tmp_path):
    case = {
        "id": "case-1",
        "expected": {
            "style_code": "wabisabi",
            "room": "客厅",
            "area_sqm": 20,
            "keywords": ["亚麻", "落地窗"],
        },
    }
    result = {
        "structured_requirement": {
            "style_code": "wabisabi",
            "room": "客厅",
            "area_sqm": 20,
            "keywords": ["亚麻", "落地窗"],
        },
        "positive_prompt": "亚麻 sofa beside 落地窗",
        "quality": {"overall": 88},
        "generation_mode": "fallback",
    }
    row = _case_metrics(case, result, 0.25)
    report = {
        "generated_at": "now",
        "case_count": 1,
        "summary": {
            "parse_accuracy": row["parse_accuracy"],
            "constraint_coverage": row["constraint_coverage"],
            "prompt_constraint_coverage": row["prompt_constraint_coverage"],
            "quality_score": row["quality_score"],
            "avg_latency_seconds": row["latency_seconds"],
            "fallback_rate": 100.0,
        },
        "cases": [row],
    }
    json_path, md_path = write_report(report, tmp_path)

    assert row["parse_accuracy"] == 100
    assert row["constraint_coverage"] == 100
    assert row["prompt_constraint_coverage"] == 100
    assert json_path.exists()
    assert "case-1" in md_path.read_text(encoding="utf-8")
