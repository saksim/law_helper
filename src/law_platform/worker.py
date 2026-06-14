from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .models import new_id, now_iso
from .store import Store

ACTIVE_JOB_STATUSES = {"queued", "running"}


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.fromisoformat(now_iso())
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(now_iso())


def _retry_after(attempts: int) -> str:
    delay_seconds = min(300, 10 * (2 ** max(attempts - 1, 0)))
    return (_parse_dt(now_iso()) + timedelta(seconds=delay_seconds)).isoformat(timespec="seconds")


def error_payload(exc: BaseException) -> dict[str, Any]:
    return {
        "code": getattr(exc, "code", exc.__class__.__name__),
        "message": getattr(exc, "message", str(exc)),
        "details": getattr(exc, "details", {}) or {},
    }


def enqueue_job(
    store: Store,
    tenant_id: str,
    case_id: str | None,
    job_type: str,
    payload: dict[str, Any],
    actor_id: str,
    run_after: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    job = {
        "id": new_id("job"),
        "tenant_id": tenant_id,
        "case_id": case_id,
        "job_type": job_type,
        "status": "queued",
        "payload": payload,
        "created_by": actor_id,
        "attempts": 0,
        "max_attempts": max_attempts,
        "run_after": run_after or now_iso(),
        "last_error": None,
        "result": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return store.insert("jobs", job)


def active_job_exists(store: Store, tenant_id: str, job_type: str, payload_key: str, payload_value: Any) -> bool:
    for job in store.list("jobs"):
        if job.get("tenant_id") != tenant_id or job.get("job_type") != job_type:
            continue
        if job.get("status") not in ACTIVE_JOB_STATUSES:
            continue
        if (job.get("payload") or {}).get(payload_key) == payload_value:
            return True
    return False


def job_is_due(job: dict[str, Any]) -> bool:
    if job.get("status") != "queued":
        return False
    return _parse_dt(job.get("run_after")) <= _parse_dt(now_iso())


def due_jobs(store: Store, tenant_id: str, limit: int) -> list[dict[str, Any]]:
    rows = [job for job in store.list("jobs") if job.get("tenant_id") == tenant_id and job_is_due(job)]
    rows.sort(key=lambda row: (row.get("run_after") or "", row.get("created_at") or ""))
    return rows[: max(1, limit)]


def start_job(store: Store, job: dict[str, Any]) -> dict[str, Any]:
    return store.update(
        "jobs",
        job["id"],
        {
            "status": "running",
            "attempts": int(job.get("attempts") or 0) + 1,
            "started_at": now_iso(),
            "updated_at": now_iso(),
        },
    )


def complete_job(store: Store, job: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return store.update(
        "jobs",
        job["id"],
        {
            "status": "succeeded",
            "result": result,
            "last_error": None,
            "finished_at": now_iso(),
            "updated_at": now_iso(),
        },
    )


def fail_job(store: Store, job: dict[str, Any], exc: BaseException) -> dict[str, Any]:
    attempts = int(job.get("attempts") or 0)
    max_attempts = int(job.get("max_attempts") or 1)
    retry = attempts < max_attempts
    updates: dict[str, Any] = {
        "status": "queued" if retry else "failed",
        "last_error": error_payload(exc),
        "updated_at": now_iso(),
    }
    if retry:
        updates["run_after"] = _retry_after(attempts)
    else:
        updates["finished_at"] = now_iso()
    return store.update("jobs", job["id"], updates)