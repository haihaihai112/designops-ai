"""RQ worker entry points.

Run with: rq worker -u redis://localhost:6379/0 interiorforge
"""

from __future__ import annotations

import asyncio


def execute_job(job_id: str, payload: dict) -> None:
    from module7_api.app import process_generation_job

    asyncio.run(process_generation_job(job_id, payload))
