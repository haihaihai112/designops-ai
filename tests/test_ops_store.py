from module3_agent.requirement_parser import parse_design_requirement
from module5_ops.report import export_project_report
from module5_ops.store import (
    add_candidate,
    create_project,
    begin_generation_job,
    dashboard_metrics,
    generation_job_cancel_requested,
    get_candidate,
    get_generation_job_by_idempotency,
    get_project,
    create_generation_job,
    get_generation_job,
    save_feedback,
    seed_legacy_batch,
    request_generation_job_cancel,
    update_generation_job,
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


def test_generation_job_lifecycle(tmp_path):
    db = tmp_path / "jobs.sqlite3"
    job_id = create_generation_job({"requirement": "侘寂风客厅"}, db)

    queued = get_generation_job(job_id, db)
    update_generation_job(job_id, status="running", progress=45, db_path=db)
    running = get_generation_job(job_id, db)

    assert queued["status"] == "queued"
    assert queued["request"]["requirement"] == "侘寂风客厅"
    assert running["status"] == "running"
    assert running["progress"] == 45


def test_job_idempotency_claim_and_cancel(tmp_path):
    db = tmp_path / "durable.sqlite3"
    first = create_generation_job(
        {"requirement": "侘寂风客厅"},
        db,
        idempotency_key="same-request",
        max_attempts=2,
        estimated_cost_usd=0.2,
    )
    duplicate = create_generation_job(
        {"requirement": "不会重复创建"},
        db,
        idempotency_key="same-request",
    )
    claimed = begin_generation_job(first, db)
    canceled = request_generation_job_cancel(first, db)

    assert duplicate == first
    assert get_generation_job_by_idempotency("same-request", db)["id"] == first
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1
    assert canceled["status"] == "cancel_requested"
    assert generation_job_cancel_requested(first, db) is True


def test_candidate_records_iteration_parent(tmp_path):
    db = tmp_path / "iterations.sqlite3"
    parsed = parse_design_requirement("20平米侘寂风客厅")
    project_id = create_project("迭代项目", parsed["raw"], parsed, db)
    parent_id = add_candidate(project_id, _result(), db)
    child = _result(90, "iteration")
    child.update(
        {
            "parent_candidate_id": parent_id,
            "iteration_instruction": "保持布局，只调整灯光",
            "generation_job_id": "job-iteration",
        }
    )
    child_id = add_candidate(project_id, child, db)

    saved = get_candidate(child_id, db)
    assert saved["parent_candidate_id"] == parent_id
    assert saved["iteration_instruction"] == "保持布局，只调整灯光"
    assert saved["generation_job_id"] == "job-iteration"
