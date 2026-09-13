from fastapi.testclient import TestClient

from module7_api import app as api_module


def test_health_contract(monkeypatch):
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(
        api_module,
        "initialize_observability",
        lambda: {"enabled": False, "active": False, "warning": ""},
    )

    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["service"] == "interiorforge-api"
    assert response.json()["observability"]["active"] is False


def test_project_not_found(monkeypatch):
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(api_module, "get_project", lambda project_id: None)

    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/projects/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "项目不存在"


def test_asset_rejects_nested_path():
    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/assets/not-an-image.txt")

    assert response.status_code == 400


def test_locked_requirement_only_includes_available_values():
    parsed = {
        "room": "客厅",
        "style_code": "wabi_sabi",
        "style_name": "侘寂风",
        "area_sqm": 20.0,
        "constraints": {
            "layout": ["通透动线"],
            "materials": ["亚麻"],
            "furniture": [],
            "lighting": ["自然光"],
        },
    }

    locked = api_module._locked_requirement(
        parsed,
        ["room", "style", "area", "layout", "materials", "furniture", "lighting"],
    )

    assert "空间类型=客厅" in locked
    assert "风格=侘寂风" in locked
    assert "面积=20平方米" in locked
    assert "layout=通透动线" in locked
    assert "materials=亚麻" in locked
    assert "lighting=自然光" in locked
    assert "furniture=" not in locked


def test_generation_job_not_found(monkeypatch):
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(api_module, "get_generation_job", lambda job_id: None)

    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/generation-jobs/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "生成任务不存在"


def test_generation_job_is_queued(monkeypatch):
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(api_module, "recover_inline_generation_jobs", lambda: [])
    monkeypatch.setattr(api_module, "get_generation_job_by_idempotency", lambda key: None)
    monkeypatch.setattr(api_module, "create_generation_job", lambda payload, **kwargs: "job-123")
    monkeypatch.setattr(
        api_module,
        "get_generation_job",
        lambda job_id: {"id": job_id, "status": "queued", "progress": 0},
    )
    monkeypatch.setattr(api_module, "_dispatch_job", lambda job_id, payload, tasks: None)

    with TestClient(api_module.app) as client:
        response = client.post(
            "/api/v1/generation-jobs",
            json={
                "requirement": "20平米侘寂风客厅",
                "candidate_count": 3,
                "locked_fields": ["room", "style", "area"],
            },
        )

    assert response.status_code == 202
    assert response.json() == {"id": "job-123", "status": "queued", "progress": 0}


def test_generation_job_idempotency_returns_existing(monkeypatch):
    existing = {"id": "same-job", "status": "running", "progress": 40}
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(api_module, "recover_inline_generation_jobs", lambda: [])
    monkeypatch.setattr(api_module, "get_generation_job_by_idempotency", lambda key: existing)

    with TestClient(api_module.app) as client:
        response = client.post(
            "/api/v1/generation-jobs",
            headers={"Idempotency-Key": "request-123"},
            json={"requirement": "20平米侘寂风客厅"},
        )

    assert response.status_code == 202
    assert response.json() == existing


def test_budget_limit_rejects_expensive_job(monkeypatch):
    monkeypatch.setitem(api_module.IMAGE_CONFIG, "estimated_cost_usd", 0.2)
    monkeypatch.setitem(api_module.BUDGET_CONFIG, "per_job_usd", 0.1)

    try:
        api_module._validate_budget(0.2, None)
        raise AssertionError("budget validation should reject the job")
    except api_module.HTTPException as exc:
        assert exc.status_code == 422


def test_iteration_candidate_not_found(monkeypatch):
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(api_module, "recover_inline_generation_jobs", lambda: [])
    monkeypatch.setattr(api_module, "get_candidate", lambda candidate_id: None)

    with TestClient(api_module.app) as client:
        response = client.post(
            "/api/v1/candidates/999/iterations",
            json={"instruction": "保持布局，只调整灯光"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "候选不存在"


def test_cancel_generation_job(monkeypatch):
    canceled = {"id": "job-1", "status": "cancel_requested", "progress": 30}
    monkeypatch.setattr(api_module, "init_db", lambda: None)
    monkeypatch.setattr(api_module, "seed_legacy_batch", lambda: 0)
    monkeypatch.setattr(api_module, "recover_inline_generation_jobs", lambda: [])
    monkeypatch.setattr(api_module, "request_generation_job_cancel", lambda job_id: canceled)
    monkeypatch.setattr(api_module, "cancel_rq_job", lambda job_id: None)

    with TestClient(api_module.app) as client:
        response = client.post("/api/v1/generation-jobs/job-1/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancel_requested"
