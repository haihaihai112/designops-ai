"""HTTP API exposing the existing DesignOps workflow with stable contracts."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import APP_CONFIG, BUDGET_CONFIG, IMAGE_CONFIG, LLM_CONFIG, PROJECT_ROOT, TASK_CONFIG
from module3_agent.agent_pipeline import run_agent
from module3_agent.requirement_parser import parse_design_requirement
from module5_ops.store import (
    add_candidate,
    begin_generation_job,
    create_generation_job,
    create_project,
    dashboard_metrics,
    generation_job_cancel_requested,
    get_candidate,
    get_candidate_for_job,
    get_generation_job,
    get_generation_job_by_idempotency,
    get_project,
    init_db,
    list_projects,
    recover_inline_generation_jobs,
    request_generation_job_cancel,
    save_feedback,
    seed_legacy_batch,
    update_generation_job,
)
from module5_ops.report import export_project_report
from module6_observability import initialize_observability
from module7_api.task_queue import cancel_rq_job, enqueue_rq_job, queue_status, uses_rq


class GenerateRequest(BaseModel):
    project_name: str = Field(default="", max_length=100)
    requirement: str = Field(min_length=4, max_length=4000)
    candidate_count: Literal[1, 3] = 1
    generate_image: bool = True
    locked_fields: list[
        Literal["room", "style", "area", "layout", "materials", "furniture", "lighting"]
    ] = Field(default_factory=list, max_length=7)
    budget_limit_usd: float | None = Field(default=None, ge=0)


class IterationRequest(BaseModel):
    instruction: str = Field(min_length=4, max_length=2000)
    generate_image: bool = True
    locked_fields: list[
        Literal["room", "style", "area", "layout", "materials", "furniture", "lighting"]
    ] = Field(default_factory=list, max_length=7)
    budget_limit_usd: float | None = Field(default=None, ge=0)


class FeedbackRequest(BaseModel):
    candidate_id: int = Field(gt=0)
    requirement_score: int = Field(ge=1, le=5)
    visual_score: int = Field(ge=1, le=5)
    feasibility_score: int = Field(ge=1, le=5)
    decision: Literal["采用", "迭代", "淘汰"]
    notes: str = Field(default="", max_length=2000)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_legacy_batch()
    initialize_observability()
    if not uses_rq():
        for job in recover_inline_generation_jobs():
            task = asyncio.create_task(process_generation_job(job["id"], job["request"]))
            _inline_tasks.add(task)
            task.add_done_callback(_inline_tasks.discard)
    yield


_inline_tasks: set[asyncio.Task] = set()


app = FastAPI(
    title="InteriorForge AI API",
    version="1.2.0",
    description="Design generation, evaluation, and model-operations API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CONFIG["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict:
    observability = initialize_observability()
    return {
        "status": "ok",
        "service": "interiorforge-api",
        "llm_backend": LLM_CONFIG["backend"],
        "llm_model": LLM_CONFIG["model"],
        "image_provider": "openai",
        "image_estimated_cost_usd": IMAGE_CONFIG["estimated_cost_usd"],
        "task_queue": queue_status(),
        "budgets": BUDGET_CONFIG,
        "observability": observability,
    }


@app.get("/api/v1/dashboard")
def dashboard() -> dict:
    metrics = dashboard_metrics()
    metrics["budget"] = {
        "monthly_limit_usd": BUDGET_CONFIG["monthly_usd"],
        "monthly_remaining_usd": (
            max(0, BUDGET_CONFIG["monthly_usd"] - metrics["estimated_cost_usd"])
            if BUDGET_CONFIG["monthly_usd"] > 0
            else None
        ),
    }
    return metrics


@app.get("/api/v1/projects")
def projects(limit: int = 50) -> list[dict]:
    return list_projects(limit=min(max(limit, 1), 100))


@app.get("/api/v1/projects/{project_id}")
def project_detail(project_id: int) -> dict:
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.get("/api/v1/projects/{project_id}/report")
def project_report(project_id: int) -> FileResponse:
    try:
        path = export_project_report(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="项目不存在") from exc
    return FileResponse(path, media_type="text/markdown", filename=path.name)


def _locked_requirement(parsed: dict, fields: list[str]) -> str:
    values = []
    category_map = {
        "layout": "layout",
        "materials": "materials",
        "furniture": "furniture",
        "lighting": "lighting",
    }
    for field in fields:
        if field == "room":
            values.append(f"空间类型={parsed['room']}")
        elif field == "style" and parsed.get("style_code"):
            values.append(f"风格={parsed['style_name']}")
        elif field == "area" and parsed.get("area_sqm") is not None:
            values.append(f"面积={parsed['area_sqm']:g}平方米")
        elif field in category_map:
            terms = parsed.get("constraints", {}).get(category_map[field], [])
            if terms:
                values.append(f"{field}={','.join(terms)}")
    return "；".join(values)


async def _generate_project(payload: GenerateRequest, job_id: str | None = None) -> dict:
    requirement = payload.requirement.strip()
    parsed = parse_design_requirement(requirement)
    parsed["locked_fields"] = list(payload.locked_fields)
    name = payload.project_name.strip() or f"{parsed['style_name']} · {parsed['room']}"
    variants = ["balanced", "creative", "practical"] if payload.candidate_count == 3 else ["balanced"]
    locked = _locked_requirement(parsed, payload.locked_fields)
    effective_requirement = requirement
    if locked:
        effective_requirement += f"\n必须保持以下锁定约束，不得修改：{locked}"

    persisted_job = get_generation_job(job_id) if job_id else None
    project_id = persisted_job.get("project_id") if persisted_job else None
    if project_id is None:
        project_id = create_project(name, requirement, parsed)
    if job_id:
        update_generation_job(job_id, status="running", progress=5, project_id=project_id)

    results = []
    errors = []
    existing = get_project(project_id)
    completed_variants = {
        item["variant"] for item in (existing or {}).get("candidates", [])
    }
    for index, variant in enumerate(variants):
        if variant in completed_variants:
            continue
        if job_id and generation_job_cancel_requested(job_id):
            raise JobCanceled("任务已由用户取消")
        try:
            result = await asyncio.to_thread(
                run_agent,
                effective_requirement,
                payload.generate_image,
                variant,
                "openai",
            )
            result["locked_fields"] = list(payload.locked_fields)
            result["generation_job_id"] = job_id
            results.append(result)
            add_candidate(project_id, result)
        except Exception as exc:
            errors.append(f"{variant}: {exc}")
        if job_id:
            progress = 5 + round((index + 1) / len(variants) * 90)
            update_generation_job(
                job_id,
                status="running",
                progress=progress,
                project_id=project_id,
                error="；".join(errors),
            )

    if not results and not (get_project(project_id) or {}).get("candidates"):
        raise RuntimeError("；".join(errors) or "没有生成可保存的候选")
    project = get_project(project_id)
    if project is None:
        raise RuntimeError("项目保存失败")
    return project


class JobCanceled(RuntimeError):
    pass


def _estimated_job_cost(candidate_count: int, generate_image: bool) -> float:
    return round(IMAGE_CONFIG["estimated_cost_usd"] * candidate_count, 4) if generate_image else 0.0


def _validate_budget(estimated_cost: float, request_limit: float | None) -> None:
    limits = [value for value in (request_limit, BUDGET_CONFIG["per_job_usd"]) if value and value > 0]
    if limits and estimated_cost > min(limits):
        raise HTTPException(
            status_code=422,
            detail=f"预计成本 ${estimated_cost:.4f} 超过单任务预算 ${min(limits):.4f}",
        )
    monthly_limit = BUDGET_CONFIG["monthly_usd"]
    if monthly_limit > 0:
        used = dashboard_metrics().get("estimated_cost_month_usd", 0) or 0
        if used + estimated_cost > monthly_limit:
            raise HTTPException(status_code=422, detail="预计成本将超过本月图片预算")


async def _generate_iteration(
    parent_candidate_id: int,
    payload: IterationRequest,
    job_id: str,
) -> dict:
    existing_result = get_candidate_for_job(job_id)
    if existing_result:
        project = get_project(existing_result["project_id"])
        if project:
            return project

    parent = get_candidate(parent_candidate_id)
    if parent is None:
        raise RuntimeError("父候选不存在")
    project = get_project(parent["project_id"])
    if project is None:
        raise RuntimeError("项目不存在")
    if generation_job_cancel_requested(job_id):
        raise JobCanceled("任务已由用户取消")

    locked_fields = payload.locked_fields or parent["result"].get("locked_fields", [])
    parsed = project["structured_requirement"]
    locked = _locked_requirement(parsed, locked_fields)
    effective_requirement = (
        f"{project['requirement']}\n基于上一版进行迭代：{payload.instruction.strip()}"
    )
    if locked:
        effective_requirement += f"\n必须保持以下锁定约束，不得修改：{locked}"

    update_generation_job(
        job_id,
        status="running",
        progress=10,
        project_id=project["id"],
    )
    result = await asyncio.to_thread(
        run_agent,
        effective_requirement,
        payload.generate_image,
        "balanced",
        "openai",
    )
    result.update(
        {
            "variant": "iteration",
            "locked_fields": list(locked_fields),
            "parent_candidate_id": parent_candidate_id,
            "iteration_instruction": payload.instruction.strip(),
            "generation_job_id": job_id,
        }
    )
    add_candidate(project["id"], result)
    updated = get_project(project["id"])
    if updated is None:
        raise RuntimeError("迭代版本保存失败")
    return updated


@app.post("/api/v1/projects/generate", status_code=201)
async def generate_project(payload: GenerateRequest) -> dict:
    try:
        return await _generate_project(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"候选生成失败：{exc}") from exc


async def process_generation_job(job_id: str, payload_data: dict) -> None:
    claimed = begin_generation_job(job_id)
    if claimed is None:
        return
    try:
        if claimed["kind"] == "iteration":
            payload = IterationRequest.model_validate(payload_data)
            project = await _generate_iteration(claimed["parent_candidate_id"], payload, job_id)
        else:
            payload = GenerateRequest.model_validate(payload_data)
            project = await _generate_project(payload, job_id)
        update_generation_job(
            job_id,
            status="completed",
            progress=100,
            project_id=project["id"],
        )
    except JobCanceled as exc:
        update_generation_job(
            job_id,
            status="canceled",
            progress=100,
            error=str(exc),
        )
    except Exception as exc:
        current = get_generation_job(job_id) or {}
        can_retry = uses_rq() and current.get("attempts", 0) < current.get("max_attempts", 1)
        update_generation_job(
            job_id,
            status="queued" if can_retry else "failed",
            progress=current.get("progress", 0) if can_retry else 100,
            error=str(exc),
        )
        if can_retry:
            raise


def _dispatch_job(
    job_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
) -> None:
    if uses_rq():
        try:
            enqueue_rq_job(job_id, payload)
        except Exception as exc:
            update_generation_job(job_id, status="failed", progress=100, error=f"任务入队失败：{exc}")
            raise HTTPException(status_code=503, detail="任务队列不可用") from exc
    else:
        background_tasks.add_task(process_generation_job, job_id, payload)


@app.post("/api/v1/generation-jobs", status_code=202)
def start_generation_job(
    payload: GenerateRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    if idempotency_key and len(idempotency_key) > 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key 不能超过 128 个字符")
    if idempotency_key:
        existing = get_generation_job_by_idempotency(idempotency_key)
        if existing:
            return existing

    data = payload.model_dump(mode="json")
    estimated_cost = _estimated_job_cost(payload.candidate_count, payload.generate_image)
    _validate_budget(estimated_cost, payload.budget_limit_usd)
    job_id = create_generation_job(
        data,
        idempotency_key=idempotency_key,
        max_attempts=TASK_CONFIG["max_retries"] + 1,
        estimated_cost_usd=estimated_cost,
    )
    _dispatch_job(job_id, data, background_tasks)
    return get_generation_job(job_id)


@app.post("/api/v1/candidates/{candidate_id}/iterations", status_code=202)
def start_candidate_iteration(
    candidate_id: int,
    payload: IterationRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    if get_candidate(candidate_id) is None:
        raise HTTPException(status_code=404, detail="候选不存在")
    if idempotency_key:
        existing = get_generation_job_by_idempotency(idempotency_key)
        if existing:
            return existing
    data = payload.model_dump(mode="json")
    estimated_cost = _estimated_job_cost(1, payload.generate_image)
    _validate_budget(estimated_cost, payload.budget_limit_usd)
    job_id = create_generation_job(
        data,
        kind="iteration",
        parent_candidate_id=candidate_id,
        idempotency_key=idempotency_key,
        max_attempts=TASK_CONFIG["max_retries"] + 1,
        estimated_cost_usd=estimated_cost,
    )
    _dispatch_job(job_id, data, background_tasks)
    return get_generation_job(job_id)


@app.get("/api/v1/generation-jobs/{job_id}")
def generation_job(job_id: str) -> dict:
    job = get_generation_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return job


@app.post("/api/v1/generation-jobs/{job_id}/cancel")
def cancel_generation_job(job_id: str) -> dict:
    job = request_generation_job_cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    cancel_rq_job(job_id)
    return job


@app.post("/api/v1/feedback", status_code=201)
def submit_feedback(payload: FeedbackRequest) -> dict:
    feedback_id = save_feedback(
        candidate_id=payload.candidate_id,
        requirement_score=payload.requirement_score,
        visual_score=payload.visual_score,
        feasibility_score=payload.feasibility_score,
        decision=payload.decision,
        notes=payload.notes,
    )
    return {"id": feedback_id, "status": "saved"}


@app.get("/api/v1/assets/{filename}")
def output_asset(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename or Path(safe_name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="无效文件名")
    candidates = [PROJECT_ROOT / "outputs" / safe_name, PROJECT_ROOT / "outputs" / "api" / safe_name]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("module7_api.app:app", host="127.0.0.1", port=8000, reload=True)
