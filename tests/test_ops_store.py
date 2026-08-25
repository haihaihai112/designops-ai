from module3_agent.requirement_parser import parse_design_requirement
from module5_ops.report import export_project_report
from module5_ops.store import (
    add_candidate,
    create_project,
    dashboard_metrics,
    get_project,
    save_feedback,
    seed_legacy_batch,
)


def _result(score: int = 82, variant: str = "balanced") -> dict:
    return {
        "variant": variant,
        "generation_mode": "fallback",
        "positive_prompt": "wabisabi living room, linen sofa, interior render",
        "negative_prompt": "low quality",
        "params": {"cfg_scale": 7, "steps": 24, "sampler": "euler_ancestral"},
        "analysis": "分析",
        "coohom_brief": "brief",
        "asset_tags": "tags",
        "social_copy": "copy",
        "rag_citations": [],
        "image": None,
        "quality": {"overall": score},
        "timings": {"total": 1.25},
    }


def test_project_versions_feedback_dashboard_and_report(tmp_path):
    db = tmp_path / "ops.sqlite3"
    parsed = parse_design_requirement("20平米侘寂风客厅，亚麻沙发")
    project_id = create_project("住宅客厅", parsed["raw"], parsed, db)
    first_id = add_candidate(project_id, _result(82), db)
    add_candidate(project_id, _result(90, "creative"), db)

    save_feedback(first_id, 5, 4, 4, "采用", "材质和尺度合理", db)
    project = get_project(project_id, db)
    metrics = dashboard_metrics(db)
    report = export_project_report(project_id, db, tmp_path / "reports")

    assert [item["version"] for item in project["candidates"]] == [1, 2]
    assert project["status"] == "adopted"
    assert project["candidates"][0]["selected"] == 1
    assert project["candidates"][0]["feedback_count"] == 1
    assert metrics["projects"] == 1
    assert metrics["candidates"] == 2
    assert metrics["adoption_rate"] == 50
    assert report.exists()
    assert "住宅客厅" in report.read_text(encoding="utf-8")


def test_seed_legacy_batch_is_idempotent(tmp_path):
    db = tmp_path / "seed.sqlite3"
    batch = tmp_path / "batch.json"
    batch.write_text(
        '[{"style":"侘寂风","room":"客厅","description":"20平米侘寂风客厅",'
        '"positive_prompt":"wabisabi living room","negative_prompt":"bad","status":"success"}]',
        encoding="utf-8",
    )

    assert seed_legacy_batch(db, batch) == 1
    assert seed_legacy_batch(db, batch) == 0
    assert dashboard_metrics(db)["candidates"] == 1
