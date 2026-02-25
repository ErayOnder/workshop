from typing import Literal
from .angles import ANGLES

# In-memory job store: { job_id: dict }
_store: dict[str, dict] = {}


def create_job(job_id: str, mode: Literal["parallel", "sequential"]) -> dict:
    job = {
        "job_id": job_id,
        "mode": mode,
        "status": "pending",
        "angles": {
            angle.key: {"status": "pending", "file": None, "error": None}
            for angle in ANGLES
        },
        "error": None,
    }
    _store[job_id] = job
    return job


def get_job(job_id: str) -> dict | None:
    return _store.get(job_id)


def set_job_status(job_id: str, status: str) -> None:
    if job_id in _store:
        _store[job_id]["status"] = status


def set_angle_done(job_id: str, angle_key: str, filename: str) -> None:
    if job_id in _store:
        _store[job_id]["angles"][angle_key] = {
            "status": "done",
            "file": filename,
            "error": None,
        }
        _maybe_complete(job_id)


def set_angle_error(job_id: str, angle_key: str, error: str) -> None:
    if job_id in _store:
        _store[job_id]["angles"][angle_key] = {
            "status": "error",
            "file": None,
            "error": error,
        }
        _maybe_complete(job_id)


def set_angle_processing(job_id: str, angle_key: str) -> None:
    if job_id in _store:
        _store[job_id]["angles"][angle_key]["status"] = "processing"


def set_job_error(job_id: str, error: str) -> None:
    if job_id in _store:
        _store[job_id]["status"] = "failed"
        _store[job_id]["error"] = error


def _maybe_complete(job_id: str) -> None:
    job = _store.get(job_id)
    if not job:
        return
    statuses = [a["status"] for a in job["angles"].values()]
    if all(s in ("done", "error") for s in statuses):
        job["status"] = "completed"
