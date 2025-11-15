"""Secure Slurm tool definitions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Any

from pydantic import Field

from ..core.app import mcp
from ..core.dependencies import get_slurm_client

MAX_SCRIPT_CHARS = 20000


@mcp.tool(description="Submit a Slurm batch job using a script body")
def slurm_submit_job(
    script: str = Field(description="Complete job script content including shebang"),
    job_name: str | None = Field(default=None, description="Optional job name"),
    partition: str | None = Field(default=None, description="Target partition"),
    nodes: int | None = Field(default=None, description="Requested nodes"),
    tasks: int | None = Field(default=None, description="Requested tasks"),
    memory: str | None = Field(default=None, description="Memory per CPU, e.g. 2G"),
    time_limit: int | None = Field(default=None, description="Time limit in minutes"),
    output: str | None = Field(default=None, description="Stdout path"),
    working_dir: str | None = Field(default=None, description="Working directory"),
) -> Dict:
    if len(script) > MAX_SCRIPT_CHARS:
        raise ValueError("script exceeds security size limit")
    client = get_slurm_client()
    return client.submit_job(
        script=script,
        job_name=job_name,
        partition=partition,
        nodes=nodes,
        tasks=tasks,
        memory=memory,
        time_limit=time_limit,
        output=output,
        working_dir=working_dir,
    )


@mcp.tool(description="Retrieve a single Slurm job")
def slurm_get_job(
    job_id: str = Field(description="Slurm job ID"),
) -> Dict:
    client = get_slurm_client()
    data = client.get_job(job_id)

    if not isinstance(data, dict):
        return {"error": "Unexpected response from Slurm", "success": False, "raw": data}

    jobs = data.get("jobs") or []
    if not jobs:
        return {"error": f"Job {job_id} not found", "success": False, "raw": data}

    job = jobs[0]
    summary = _summarize_job(job)

    status_text = _format_status(summary)

    return {
        "success": True,
        "job_id": summary["job_id"],
        "status": summary,
        "status_text": status_text,
        "raw": job,
        "warnings": data.get("warnings", []),
    }


@mcp.tool(description="List Slurm jobs with optional filters")
def slurm_list_jobs(
    state: str | None = Field(default=None, description="Filter by job state"),
    user: str | None = Field(default=None, description="Filter by username"),
) -> Dict:
    client = get_slurm_client()
    data = client.list_jobs()
    jobs: List[Dict] = data.get("jobs", []) if isinstance(data, dict) else []
    if state:
        jobs = [job for job in jobs if job.get("job_state") == state.upper()]
    if user:
        jobs = [job for job in jobs if job.get("user_name") == user]
    data["jobs"] = jobs
    return data


@mcp.tool(description="Cancel a Slurm job")
def slurm_cancel_job(
    job_id: str = Field(description="Slurm job ID"),
) -> Dict:
    client = get_slurm_client()
    return client.cancel_job(job_id)


@mcp.tool(description="Summarize Slurm queue state")
def slurm_queue_summary() -> Dict:
    client = get_slurm_client()
    data = client.list_jobs()
    jobs: List[Dict] = data.get("jobs", []) if isinstance(data, dict) else []
    summary = {
        "total_jobs": len(jobs),
        "running": sum(1 for job in jobs if job.get("job_state") == "RUNNING"),
        "pending": sum(1 for job in jobs if job.get("job_state") == "PENDING"),
        "completed": sum(1 for job in jobs if job.get("job_state") == "COMPLETED"),
    }
    return {"summary": summary, "sample": jobs[:20]}


def _summarize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    submit_secs, submit_time = _timestamp(job.get("submit_time"))
    start_secs, start_time = _timestamp(job.get("start_time"))
    end_secs, end_time = _timestamp(job.get("end_time"))

    duration_seconds: int | None = None
    if start_secs is not None and end_secs is not None:
        duration_seconds = max(0, int(end_secs - start_secs))

    job_state = job.get("job_state")
    if isinstance(job_state, list):
        job_state = ",".join(job_state)

    exit_code = job.get("exit_code")
    if isinstance(exit_code, dict):
        exit_code = _numeric(exit_code.get("return_code"))
    else:
        exit_code = _numeric(exit_code)

    summary = {
        "job_id": job.get("job_id"),
        "name": job.get("name"),
        "user": job.get("user_name"),
        "state": job_state,
        "partition": job.get("partition"),
        "nodes": _numeric(job.get("node_count")) or job.get("nodes"),
        "ntasks": _numeric(job.get("tasks")),
        "cpus": _numeric(job.get("cpus")),
        "memory": job.get("memory_per_node") or job.get("memory_per_tres"),
        "submit_time": submit_time,
        "start_time": start_time,
        "end_time": end_time,
        "runtime_seconds": duration_seconds,
        "stdout": job.get("stdout_expanded") or job.get("standard_output"),
        "stderr": job.get("stderr_expanded") or job.get("standard_error"),
        "node_list": job.get("nodes"),
        "exit_code": exit_code,
    }

    return summary


def _format_status(summary: Dict[str, Any]) -> str:
    parts = [
        f"Job {summary.get('job_id')} ({summary.get('name')})",
        f"user={summary.get('user')}",
        f"state={summary.get('state')}",
    ]

    if summary.get("partition"):
        parts.append(f"partition={summary['partition']}")
    if summary.get("nodes"):
        parts.append(f"nodes={summary['nodes']}")
    if summary.get("ntasks"):
        parts.append(f"tasks={summary['ntasks']}")
    if summary.get("runtime_seconds") is not None:
        parts.append(f"runtime={_format_duration(summary['runtime_seconds'])}")

    return ", ".join(parts)


def _timestamp(field: Any) -> tuple[int | None, str | None]:
    seconds = _numeric(field)
    if seconds is None:
        return None, None
    try:
        iso = datetime.fromtimestamp(int(seconds), tz=timezone.utc).isoformat()
    except Exception:
        iso = str(seconds)
    return int(seconds), iso


def _numeric(value: Any) -> int | float | None:
    if isinstance(value, dict):
        if not value.get("set", True):
            return None
        value = value.get("number")
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if value is False:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _format_duration(seconds: int) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or (hours and secs):
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return "".join(parts)
