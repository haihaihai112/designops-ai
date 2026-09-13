"""Optional Redis/RQ boundary for durable generation tasks."""

from __future__ import annotations

from config import TASK_CONFIG


def uses_rq() -> bool:
    return TASK_CONFIG["backend"] == "rq"


def enqueue_rq_job(job_id: str, payload: dict) -> None:
    if not uses_rq():
        raise RuntimeError("RQ 任务队列未启用")

    from redis import Redis
    from rq import Queue, Retry

    connection = Redis.from_url(TASK_CONFIG["redis_url"])
    connection.ping()
    queue = Queue(TASK_CONFIG["queue_name"], connection=connection)
    retry = (
        Retry(max=TASK_CONFIG["max_retries"], interval=[5, 20, 60])
        if TASK_CONFIG["max_retries"] > 0
        else None
    )
    queue.enqueue(
        "module7_api.worker.execute_job",
        job_id,
        payload,
        job_id=job_id,
        job_timeout=TASK_CONFIG["timeout_seconds"],
        retry=retry,
        result_ttl=3600,
        failure_ttl=86400,
    )


def cancel_rq_job(job_id: str) -> None:
    if not uses_rq():
        return
    try:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(TASK_CONFIG["redis_url"])
        Job.fetch(job_id, connection=connection).cancel()
    except Exception:
        # The persisted cancellation flag is authoritative; the worker checks it
        # between candidates even if the broker job has already started.
        return


def queue_status() -> dict:
    status = {"backend": TASK_CONFIG["backend"], "connected": False, "warning": ""}
    if not uses_rq():
        status["connected"] = True
        return status
    try:
        from redis import Redis

        Redis.from_url(TASK_CONFIG["redis_url"]).ping()
        status["connected"] = True
    except Exception as exc:
        status["warning"] = str(exc)
    return status
