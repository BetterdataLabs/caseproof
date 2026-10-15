"""Private agent worker. Receives a job id from the queue, never document content.

Locally the dispatcher calls /jobs/execute with mode=async (the worker acknowledges and runs the job in the
background; a crash is recovered by lease expiry). Under Cloud Tasks the request is synchronous, so the task
is acknowledged only after the next state or retry obligation is committed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .automation.runner import execute_job
from .config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("caseproof.worker")
settings = get_settings()
app = FastAPI(title="CaseProof worker", docs_url=None, redoc_url=None)
_slots = asyncio.Semaphore(settings.global_concurrency)  # one invocation per slot
_running: set[asyncio.Task] = set()


def _authorise(authorization: str | None) -> None:
    if settings.queue_backend == "cloudtasks":
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        token = (authorization or "").removeprefix("Bearer ")
        try:
            claims = id_token.verify_oauth2_token(
                token, google_requests.Request(), audience=settings.worker_url
            )
        except Exception as exc:
            raise HTTPException(status_code=401, detail="invalid task identity") from exc
        if claims.get("email") != settings.cloud_tasks_service_account:
            raise HTTPException(status_code=403, detail="unexpected task identity")
        return
    if authorization != f"Bearer {settings.internal_token}":
        raise HTTPException(status_code=401, detail="internal endpoint")


class ExecuteIn(BaseModel):
    job_id: str
    mode: str = "sync"


async def _run(job_id: uuid.UUID) -> dict:
    async with _slots:
        try:
            result = await execute_job(job_id)
            log.info("job %s → %s", job_id, result)
            return result
        except Exception:
            log.exception("job %s crashed; the lease will expire and the reconciler resumes it", job_id)
            return {"status": "CRASHED"}


@app.post("/jobs/execute")
async def execute(body: ExecuteIn, authorization: str | None = Header(default=None)) -> dict:
    _authorise(authorization)
    job_id = uuid.UUID(body.job_id)
    if body.mode == "async" and settings.queue_backend == "local":
        task = asyncio.create_task(_run(job_id))
        _running.add(task)
        task.add_done_callback(_running.discard)
        return {"status": "ACCEPTED"}
    return await _run(job_id)


@app.post("/jobs/reconcile")
async def reconcile(authorization: str | None = Header(default=None)) -> dict:
    """Cloud Scheduler entry point (once per minute): missed dispatch, expired leases and due timers."""
    _authorise(authorization)
    from .dispatcher import reconcile_once

    return await asyncio.to_thread(reconcile_once)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "running": len(_running)}
