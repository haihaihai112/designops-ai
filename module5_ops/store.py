"""SQLite persistence for projects, generated candidates, and human feedback."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import PROJECT_ROOT


DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "designops_ops.sqlite3"
LEGACY_DB_PATH = PROJECT_ROOT / "data" / "interiorforge_ops.sqlite3"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def migrate_legacy_db() -> Path:
    """Move the pre-rename runtime database to the DesignOps filename once."""
    if not DEFAULT_DB_PATH.exists() and LEGACY_DB_PATH.exists():
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEGACY_DB_PATH.replace(DEFAULT_DB_PATH)
    return DEFAULT_DB_PATH


@contextmanager
def _connect(db_path: str | Path = DEFAULT_DB_PATH):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Create the operations schema if it does not exist."""
    if Path(db_path) == DEFAULT_DB_PATH:
        migrate_legacy_db()
    with _connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                requirement TEXT NOT NULL,
                structured_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                variant TEXT NOT NULL DEFAULT 'balanced',
                result_json TEXT NOT NULL,
                auto_score REAL,
                image_path TEXT,
                generation_mode TEXT NOT NULL DEFAULT 'unknown',
                duration_seconds REAL NOT NULL DEFAULT 0,
                selected INTEGER NOT NULL DEFAULT 0,
                parent_candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
                iteration_instruction TEXT NOT NULL DEFAULT '',
                generation_job_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(project_id, version)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                requirement_score INTEGER NOT NULL,
                visual_score INTEGER NOT NULL,
                feasibility_score INTEGER NOT NULL,
                decision TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS generation_jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'generation',
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                request_json TEXT NOT NULL,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                parent_candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                idempotency_key TEXT,
                estimated_cost_usd REAL NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_candidates_project ON candidates(project_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_candidate ON feedback(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(status);
            """
        )
        migrations = {
            "candidates": {
                "parent_candidate_id": "INTEGER REFERENCES candidates(id) ON DELETE SET NULL",
                "iteration_instruction": "TEXT NOT NULL DEFAULT ''",
                "generation_job_id": "TEXT",
            },
            "generation_jobs": {
                "kind": "TEXT NOT NULL DEFAULT 'generation'",
                "parent_candidate_id": "INTEGER REFERENCES candidates(id) ON DELETE SET NULL",
                "attempts": "INTEGER NOT NULL DEFAULT 0",
                "max_attempts": "INTEGER NOT NULL DEFAULT 3",
                "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
                "idempotency_key": "TEXT",
                "estimated_cost_usd": "REAL NOT NULL DEFAULT 0",
            },
        }
        for table, columns in migrations.items():
            existing = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_jobs_idempotency
               ON generation_jobs(idempotency_key) WHERE idempotency_key IS NOT NULL"""
        )
    return Path(db_path)


def create_project(
    name: str,
    requirement: str,
    structured_requirement: dict,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    init_db(db_path)
    timestamp = _now()
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """INSERT INTO projects(name, requirement, structured_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (name.strip() or requirement[:24], requirement, json.dumps(structured_requirement, ensure_ascii=False), timestamp, timestamp),
        )
        return int(cursor.lastrowid)


def add_candidate(project_id: int, result: dict, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    init_db(db_path)
    image = result.get("image") or {}
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM candidates WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        version = int(row["version"])
        cursor = connection.execute(
            """INSERT INTO candidates(
                   project_id, version, variant, result_json, auto_score, image_path,
                   generation_mode, duration_seconds, parent_candidate_id,
                   iteration_instruction, generation_job_id, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                version,
                result.get("variant", "balanced"),
                json.dumps(result, ensure_ascii=False),
                result.get("decision_score", result.get("quality", {}).get("overall")),
                image.get("image_path") or result.get("image_path"),
                result.get("generation_mode", "unknown"),
                result.get("timings", {}).get("total", 0),
                result.get("parent_candidate_id"),
                result.get("iteration_instruction", ""),
                result.get("generation_job_id"),
                _now(),
            ),
        )
        connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (_now(), project_id))
        return int(cursor.lastrowid)


def save_feedback(
    candidate_id: int,
    requirement_score: int,
    visual_score: int,
    feasibility_score: int,
    decision: str,
    notes: str = "",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    init_db(db_path)
    timestamp = _now()
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """INSERT INTO feedback(
                   candidate_id, requirement_score, visual_score, feasibility_score,
                   decision, notes, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (candidate_id, requirement_score, visual_score, feasibility_score, decision, notes.strip(), timestamp),
        )
        if decision == "采用":
            project = connection.execute(
                "SELECT project_id FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            if project:
                connection.execute("UPDATE candidates SET selected = 0 WHERE project_id = ?", (project["project_id"],))
                connection.execute("UPDATE candidates SET selected = 1 WHERE id = ?", (candidate_id,))
                connection.execute(
                    "UPDATE projects SET status = 'adopted', updated_at = ? WHERE id = ?",
                    (timestamp, project["project_id"]),
                )
        return int(cursor.lastrowid)


def create_generation_job(
    payload: dict,
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    kind: str = "generation",
    parent_candidate_id: int | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 3,
    estimated_cost_usd: float = 0,
) -> str:
    init_db(db_path)
    normalized_key = idempotency_key.strip() if idempotency_key else None
    if normalized_key:
        with _connect(db_path) as connection:
            existing = connection.execute(
                "SELECT id FROM generation_jobs WHERE idempotency_key = ?",
                (normalized_key,),
            ).fetchone()
        if existing:
            return str(existing["id"])
    job_id = uuid.uuid4().hex
    timestamp = _now()
    with _connect(db_path) as connection:
        connection.execute(
            """INSERT INTO generation_jobs(
                   id, kind, status, progress, request_json, parent_candidate_id,
                   max_attempts, idempotency_key, estimated_cost_usd, created_at, updated_at
               ) VALUES (?, ?, 'queued', 0, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                kind,
                json.dumps(payload, ensure_ascii=False),
                parent_candidate_id,
                max(1, max_attempts),
                normalized_key,
                max(0, float(estimated_cost_usd)),
                timestamp,
                timestamp,
            ),
        )
    return job_id


def update_generation_job(
    job_id: str,
    *,
    status: str,
    progress: int,
    project_id: int | None = None,
    error: str = "",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """UPDATE generation_jobs
               SET status = ?, progress = ?, project_id = COALESCE(?, project_id),
                   error = ?, updated_at = ?
               WHERE id = ?""",
            (status, min(100, max(0, progress)), project_id, error, _now(), job_id),
        )


def get_generation_job(job_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM generation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["request"] = json.loads(data.pop("request_json"))
    data["cancel_requested"] = bool(data["cancel_requested"])
    return data


def get_generation_job_by_idempotency(
    idempotency_key: str, db_path: str | Path = DEFAULT_DB_PATH
) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT id FROM generation_jobs WHERE idempotency_key = ?",
            (idempotency_key.strip(),),
        ).fetchone()
    return get_generation_job(str(row["id"]), db_path) if row else None


def begin_generation_job(job_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    """Atomically claim a job attempt unless it is already terminal or canceled."""
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT status, attempts, max_attempts, cancel_requested FROM generation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not row or row["status"] in {"completed", "failed", "canceled"}:
            return None
        if row["cancel_requested"]:
            connection.execute(
                "UPDATE generation_jobs SET status = 'canceled', progress = 100, updated_at = ? WHERE id = ?",
                (_now(), job_id),
            )
            return None
        attempts = int(row["attempts"]) + 1
        if attempts > int(row["max_attempts"]):
            connection.execute(
                """UPDATE generation_jobs SET status = 'failed', progress = 100,
                   error = '超过最大重试次数', updated_at = ? WHERE id = ?""",
                (_now(), job_id),
            )
            return None
        connection.execute(
            """UPDATE generation_jobs SET status = 'running', progress = MAX(progress, 1),
               attempts = ?, error = '', updated_at = ? WHERE id = ?""",
            (attempts, _now(), job_id),
        )
    return get_generation_job(job_id, db_path)


def request_generation_job_cancel(job_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT status FROM generation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            return None
        if row["status"] not in {"completed", "failed", "canceled"}:
            if row["status"] == "queued":
                connection.execute(
                    """UPDATE generation_jobs SET cancel_requested = 1,
                       status = 'canceled', progress = 100, updated_at = ? WHERE id = ?""",
                    (_now(), job_id),
                )
            else:
                connection.execute(
                    """UPDATE generation_jobs SET cancel_requested = 1,
                       status = 'cancel_requested', updated_at = ? WHERE id = ?""",
                    (_now(), job_id),
                )
    return get_generation_job(job_id, db_path)


def generation_job_cancel_requested(job_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> bool:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT cancel_requested FROM generation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return bool(row and row["cancel_requested"])


def recover_inline_generation_jobs(db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    """Requeue incomplete in-process tasks after an API restart."""
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            """UPDATE generation_jobs SET status = 'queued', updated_at = ?
               WHERE status IN ('running', 'cancel_requested') AND cancel_requested = 0""",
            (_now(),),
        )
        rows = connection.execute(
            """SELECT id FROM generation_jobs
               WHERE status = 'queued' AND cancel_requested = 0 ORDER BY created_at"""
        ).fetchall()
    return [job for row in rows if (job := get_generation_job(row["id"], db_path))]


def get_candidate_for_job(job_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT id FROM candidates WHERE generation_job_id = ? ORDER BY version DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    return get_candidate(int(row["id"]), db_path) if row else None


def list_projects(db_path: str | Path = DEFAULT_DB_PATH, limit: int = 100) -> list[dict]:
    init_db(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """SELECT p.*, COUNT(c.id) AS candidate_count,
                      ROUND(MAX(c.auto_score), 1) AS best_score,
                      SUM(CASE WHEN c.selected = 1 THEN 1 ELSE 0 END) AS selected_count
               FROM projects p
               LEFT JOIN candidates c ON c.project_id = p.id
               GROUP BY p.id
               ORDER BY p.updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_project(project_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        project = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            return None
        candidates = connection.execute(
            """SELECT c.*,
                      ROUND(AVG((f.requirement_score + f.visual_score + f.feasibility_score) / 3.0), 2) AS human_score,
                      COUNT(f.id) AS feedback_count
               FROM candidates c
               LEFT JOIN feedback f ON f.candidate_id = c.id
               WHERE c.project_id = ?
               GROUP BY c.id
               ORDER BY c.version""",
            (project_id,),
        ).fetchall()
    data = dict(project)
    data["structured_requirement"] = json.loads(data.pop("structured_json"))
    data["candidates"] = []
    for row in candidates:
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json"))
        data["candidates"].append(item)
    return data


def get_candidate(candidate_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            """SELECT c.*, p.name AS project_name, p.requirement
               FROM candidates c JOIN projects p ON p.id = c.project_id
               WHERE c.id = ?""",
            (candidate_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["result"] = json.loads(data.pop("result_json"))
    return data


def dashboard_metrics(db_path: str | Path = DEFAULT_DB_PATH) -> dict:
    init_db(db_path)
    with _connect(db_path) as connection:
        totals = connection.execute(
            """SELECT COUNT(DISTINCT p.id) AS projects,
                      COUNT(c.id) AS candidates,
                      ROUND(AVG(c.auto_score), 1) AS auto_score,
                      ROUND(AVG(c.duration_seconds), 2) AS avg_duration,
                      ROUND(100.0 * AVG(CASE WHEN c.generation_mode = 'fallback' THEN 1 ELSE 0 END), 1) AS fallback_rate,
                      ROUND(100.0 * AVG(CASE WHEN c.selected = 1 THEN 1 ELSE 0 END), 1) AS adoption_rate
               FROM projects p LEFT JOIN candidates c ON c.project_id = p.id"""
        ).fetchone()
        human = connection.execute(
            """SELECT ROUND(AVG((requirement_score + visual_score + feasibility_score) / 3.0), 2) AS score,
                      COUNT(*) AS count
               FROM feedback"""
        ).fetchone()
        decisions = connection.execute(
            "SELECT decision, COUNT(*) AS count FROM feedback GROUP BY decision ORDER BY count DESC"
        ).fetchall()
        recent = connection.execute(
            """SELECT c.id, p.name, c.version, c.variant, c.auto_score, c.generation_mode,
                      c.duration_seconds, c.selected, c.created_at
               FROM candidates c JOIN projects p ON p.id = c.project_id
               ORDER BY c.created_at DESC LIMIT 10"""
        ).fetchall()
        styles = connection.execute("SELECT structured_json FROM projects").fetchall()
        result_rows = connection.execute("SELECT result_json, created_at FROM candidates").fetchall()

    style_counts = {}
    for row in styles:
        style = json.loads(row["structured_json"] or "{}").get("style_name", "未指定")
        style_counts[style] = style_counts.get(style, 0) + 1
    estimated_cost = 0.0
    estimated_cost_month = 0.0
    generated_images = 0
    successful_images = 0
    for row in result_rows:
        result = json.loads(row["result_json"] or "{}")
        item_cost = float(result.get("costs", {}).get("image_estimated_usd", 0) or 0)
        estimated_cost += item_cost
        if str(row["created_at"]).startswith(datetime.now().astimezone().strftime("%Y-%m")):
            estimated_cost_month += item_cost
        image = result.get("image") or {}
        if image:
            generated_images += 1
            successful_images += int(bool(image.get("success")))
    return {
        **dict(totals),
        "human_score": human["score"],
        "feedback_count": human["count"],
        "decisions": [dict(row) for row in decisions],
        "recent": [dict(row) for row in recent],
        "styles": style_counts,
        "estimated_cost_usd": round(estimated_cost, 4),
        "estimated_cost_month_usd": round(estimated_cost_month, 4),
        "image_success_rate": (
            round(successful_images / generated_images * 100, 1) if generated_images else None
        ),
    }


def seed_legacy_batch(db_path: str | Path = DEFAULT_DB_PATH, batch_path: str | Path | None = None) -> int:
    """Import the existing batch portfolio once so the dashboard starts with real history."""
    init_db(db_path)
    batch_file = Path(batch_path) if batch_path else PROJECT_ROOT / "outputs" / "batch_results.json"
    if not batch_file.exists():
        return 0
    with _connect(db_path) as connection:
        seeded = connection.execute("SELECT value FROM metadata WHERE key = 'legacy_batch_seeded'").fetchone()
        if seeded:
            return 0

    from module3_agent.quality_evaluator import evaluate_design_bundle
    from module3_agent.requirement_parser import parse_design_requirement

    records = json.loads(batch_file.read_text(encoding="utf-8"))
    imported = 0
    for record in records:
        requirement = record.get("description") or record.get("design", {}).get("desc")
        if not requirement:
            continue
        legacy_image = record.get("image_path")
        if legacy_image:
            local_image = PROJECT_ROOT / "outputs" / Path(legacy_image).name
            image_path = str(local_image) if local_image.exists() else legacy_image
        else:
            image_path = None
        parsed = parse_design_requirement(requirement)
        result = {
            "user_input": requirement,
            "detected_style": parsed["style_code"],
            "detected_room": parsed["room"],
            "structured_requirement": parsed,
            "positive_prompt": record.get("positive_prompt", ""),
            "negative_prompt": record.get("negative_prompt", ""),
            "params": record.get("params", {}),
            "analysis": record.get("analysis", ""),
            "coohom_brief": record.get("coohom_brief", ""),
            "asset_tags": record.get("asset_tags", ""),
            "social_copy": record.get("social_copy", ""),
            "image_path": image_path,
            "image": {"success": bool(image_path), "image_path": image_path},
            "rag_citations": [],
            "generation_mode": "legacy",
            "variant": "balanced",
            "timings": {"total": 0},
        }
        result["quality"] = evaluate_design_bundle(parsed, result)
        project_id = create_project(
            f"{record.get('style', parsed['style_name'])} · {record.get('room', parsed['room'])}",
            requirement,
            parsed,
            db_path,
        )
        add_candidate(project_id, result, db_path)
        imported += 1

    with _connect(db_path) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('legacy_batch_seeded', ?)", (_now(),)
        )
    return imported
