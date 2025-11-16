"""Slurm backend adapter using REST API"""

import httpx
import jwt
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from .base import (
    BackendAdapter,
    JobSubmitParams,
    JobSubmitResult,
    JobDetails,
)


class SlurmAdapter(BackendAdapter):
    """Slurm backend adapter using REST API v0.0.40+"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Slurm adapter

        Args:
            config: Configuration dict with:
                - endpoint: Slurm REST API URL (e.g., http://slurm-restapi.slurm.svc.cluster.local:6820)
                - auth: Optional auth config with:
                    - user: Username for JWT token
                    - jwt_token: Pre-generated JWT token (optional)
                    - jwt_auto_generate: Auto-generate token if True (requires k8s access)
        """
        super().__init__(config)
        self.endpoint = config["endpoint"].rstrip("/")
        self.auth_config = config.get("auth", {})
        self.jwt_token = self.auth_config.get("jwt_token")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _get_jwt_token(self) -> str:
        """
        Get JWT token for Slurm REST API authentication

        Returns:
            JWT token string

        Raises:
            Exception: If token generation fails
        """
        if self.jwt_token:
            return self.jwt_token

        # Auto-generate JWT token (simplified - production would use scontrol token)
        user = self.auth_config.get("user", "slurm")
        payload = {
            "sun": user,  # Slurm User Name
            "exp": int(time.time()) + 86400,  # 24 hour expiration
        }
        # Note: This is a simplified token. Real implementation would use Slurm's key
        self.jwt_token = jwt.encode(payload, "slurm_secret", algorithm="HS256")
        return self.jwt_token

    async def _make_request(
        self, method: str, path: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Slurm REST API

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API path (without base URL)
            **kwargs: Additional arguments for httpx request

        Returns:
            Response JSON

        Raises:
            Exception: If request fails
        """
        token = await self._get_jwt_token()
        headers = kwargs.pop("headers", {})
        headers["X-SLURM-USER-TOKEN"] = token
        headers["X-SLURM-USER-NAME"] = self.auth_config.get("user", "slurm")

        url = f"{self.endpoint}{path}"
        response = await self.client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def _normalize_state(self, slurm_state: str) -> str:
        """Normalize Slurm job state to unified format"""
        state_map = {
            "PENDING": "PENDING",
            "RUNNING": "RUNNING",
            "COMPLETED": "COMPLETED",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
            "TIMEOUT": "TIMEOUT",
            "NODE_FAIL": "FAILED",
            "PREEMPTED": "CANCELLED",
            "COMPLETING": "RUNNING",
            "CONFIGURING": "PENDING",
        }
        return state_map.get(slurm_state, slurm_state)

    def _format_timestamp(self, timestamp_dict: Dict[str, Any]) -> str:
        """Convert Slurm timestamp to ISO8601"""
        if not timestamp_dict or not timestamp_dict.get("set"):
            return ""
        ts = timestamp_dict.get("number", 0)
        if ts == 0:
            return ""
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    def _calculate_runtime(self, start_time: int, end_time: int = None) -> str:
        """Calculate runtime in HH:MM:SS format"""
        if start_time == 0:
            return "00:00:00"

        end = end_time if end_time and end_time > 0 else int(time.time())
        duration = max(0, end - start_time)

        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    async def submit_job(self, params: JobSubmitParams) -> JobSubmitResult:
        """Submit a job to Slurm via REST API"""
        try:
            # Build job submission payload
            job_spec = {
                "script": params.script,
                "current_working_directory": params.working_dir or "/tmp",
            }

            if params.job_name:
                job_spec["name"] = params.job_name
            if params.nodes:
                job_spec["nodes"] = params.nodes
            if params.tasks_per_node:
                job_spec["tasks_per_node"] = params.tasks_per_node
            if params.cpus_per_task:
                job_spec["cpus_per_task"] = params.cpus_per_task
            if params.memory:
                job_spec["memory_per_node"] = params.memory
            if params.time_limit:
                job_spec["time_limit"] = params.time_limit
            if params.partition:
                job_spec["partition"] = params.partition
            if params.output_path:
                job_spec["standard_output"] = params.output_path
            if params.error_path:
                job_spec["standard_error"] = params.error_path

            payload = {"job": job_spec}

            # Submit via REST API (using v0.0.40 endpoint)
            response = await self._make_request(
                "POST", "/slurm/v0.0.40/job/submit", json=payload
            )

            # Extract job_id from response
            errors = response.get("errors", [])
            if errors:
                error_msg = "; ".join(e.get("error", str(e)) for e in errors)
                return JobSubmitResult(success=False, error=error_msg)

            job_id = str(response.get("job_id", ""))
            if not job_id:
                return JobSubmitResult(success=False, error="No job_id in response")

            return JobSubmitResult(success=True, job_id=job_id, state="PENDING")

        except Exception as e:
            return JobSubmitResult(success=False, error=str(e))

    async def get_job(self, job_id: str) -> JobDetails:
        """Get job information from Slurm"""
        response = await self._make_request("GET", f"/slurm/v0.0.40/job/{job_id}")

        jobs = response.get("jobs", [])
        if not jobs:
            raise Exception(f"Job {job_id} not found")

        job_data = jobs[0]

        # Extract basic fields
        submitted_ts = job_data.get("submit_time", {})
        start_ts = job_data.get("start_time", {})
        end_ts = job_data.get("end_time", {})

        start_num = start_ts.get("number", 0) if start_ts else 0
        end_num = end_ts.get("number", 0) if end_ts else 0

        # Determine exit code
        exit_code = None
        exit_code_info = job_data.get("exit_code", {})
        if isinstance(exit_code_info, dict):
            return_code = exit_code_info.get("return_code")
            if return_code is not None and return_code != "PENDING":
                exit_code = int(return_code) if str(return_code).isdigit() else None

        # Build JobDetails
        details = JobDetails(
            job_id=str(job_data.get("job_id", job_id)),
            name=job_data.get("name", ""),
            state=self._normalize_state(
                job_data.get("job_state", ["UNKNOWN"])[0]
                if isinstance(job_data.get("job_state"), list)
                else job_data.get("job_state", "UNKNOWN")
            ),
            submitted=self._format_timestamp(submitted_ts),
            runtime=self._calculate_runtime(start_num, end_num),
            exit_code=exit_code,
            user=job_data.get("user_name", ""),
            partition=job_data.get("partition", ""),
            started=self._format_timestamp(start_ts),
            ended=self._format_timestamp(end_ts) if end_num > 0 else None,
            time_limit=job_data.get("time_limit", {}).get("number", "00:00:00"),
            resources={
                "nodes": job_data.get("node_count", {}).get("number", 0),
                "tasks": job_data.get("tasks", 0),
                "cpus_per_task": job_data.get("cpus_per_task", 0),
                "memory": job_data.get("memory_per_node", ""),
            },
            allocated_nodes=job_data.get("nodes", "").split(",")
            if job_data.get("nodes")
            else [],
            working_directory=job_data.get("current_working_directory", ""),
            stdout_path=job_data.get("standard_output", ""),
            stderr_path=job_data.get("standard_error", ""),
        )

        return details

    async def list_jobs(
        self,
        user: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobDetails]:
        """List jobs from Slurm"""
        # Note: Slurm REST API filtering is limited, we filter client-side
        response = await self._make_request("GET", "/slurm/v0.0.40/jobs")

        jobs = response.get("jobs", [])
        result = []

        for job_data in jobs[:limit]:
            try:
                job_id = str(job_data.get("job_id", ""))
                if not job_id:
                    continue

                # Apply filters
                if user and job_data.get("user_name") != user:
                    continue

                job_state = self._normalize_state(
                    job_data.get("job_state", ["UNKNOWN"])[0]
                    if isinstance(job_data.get("job_state"), list)
                    else job_data.get("job_state", "UNKNOWN")
                )
                if state and job_state != state:
                    continue

                # Create minimal JobDetails (concise format)
                submitted_ts = job_data.get("submit_time", {})
                start_ts = job_data.get("start_time", {})
                start_num = start_ts.get("number", 0) if start_ts else 0

                details = JobDetails(
                    job_id=job_id,
                    name=job_data.get("name", ""),
                    state=job_state,
                    submitted=self._format_timestamp(submitted_ts),
                    runtime=self._calculate_runtime(start_num),
                    exit_code=None,
                )
                result.append(details)

            except Exception:
                continue  # Skip malformed job entries

        return result[:limit]

    async def cancel_job(self, job_id: str, signal: str = "TERM") -> Dict[str, Any]:
        """Cancel a job in Slurm"""
        try:
            response = await self._make_request(
                "DELETE", f"/slurm/v0.0.40/job/{job_id}"
            )

            errors = response.get("errors", [])
            if errors:
                error_msg = "; ".join(e.get("error", str(e)) for e in errors)
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": error_msg,
                }

            return {
                "success": True,
                "job_id": job_id,
                "state": "CANCELLED",
                "message": f"Job {job_id} cancelled",
            }

        except Exception as e:
            return {"success": False, "job_id": job_id, "error": str(e)}

    async def get_job_output(
        self, job_id: str, output_type: str = "stdout", tail_lines: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve job output from Slurm

        Note: This is a placeholder - actual implementation would need to read
        the output files from the filesystem, which requires different permissions
        """
        # Get job details to find output paths
        job = await self.get_job(job_id)

        result = {
            "success": False,
            "job_id": job_id,
            "error": "Output retrieval not implemented - requires filesystem access",
        }

        if output_type in ["stdout", "both"]:
            result["stdout_path"] = job.stdout_path
        if output_type in ["stderr", "both"]:
            result["stderr_path"] = job.stderr_path

        return result

    async def get_queue_status(self, response_format: str = "concise") -> Dict[str, Any]:
        """
        Get queue statistics and utilization overview

        Args:
            response_format: "concise" (default) or "detailed"

        Returns:
            Dict with queue statistics

        Raises:
            NotImplementedError: This method is not yet implemented for Slurm
        """
        raise NotImplementedError(
            "get_queue_status is not yet implemented for Slurm adapter. "
            "Use MockAdapter with USE_MOCK_BACKENDS=true for testing."
        )

    async def get_resources(self, response_format: str = "concise") -> Dict[str, Any]:
        """
        Get cluster resource availability and configuration

        Args:
            response_format: "concise" (default) or "detailed"

        Returns:
            Dict with resource information

        Raises:
            NotImplementedError: This method is not yet implemented for Slurm
        """
        raise NotImplementedError(
            "get_resources is not yet implemented for Slurm adapter. "
            "Use MockAdapter with USE_MOCK_BACKENDS=true for testing."
        )

    async def get_accounting(
        self,
        job_id: Optional[str] = None,
        user: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        response_format: str = "concise",
    ) -> Dict[str, Any]:
        """
        Get historical job accounting and performance data

        Args:
            job_id: Specific job ID to query
            user: Filter by username
            start_time: Start of time range (ISO8601)
            end_time: End of time range (ISO8601)
            limit: Maximum records to return
            response_format: "concise" (default) or "detailed"

        Returns:
            Dict with accounting data

        Raises:
            NotImplementedError: This method is not yet implemented for Slurm
        """
        raise NotImplementedError(
            "get_accounting is not yet implemented for Slurm adapter. "
            "Use MockAdapter with USE_MOCK_BACKENDS=true for testing."
        )

    async def submit_batch(
        self,
        script: str,
        array_spec: Optional[str] = None,
        commands: Optional[List[str]] = None,
        job_name_prefix: Optional[str] = None,
        nodes: Optional[int] = None,
        tasks_per_node: Optional[int] = None,
        time_limit: Optional[str] = None,
        max_concurrent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Submit multiple jobs as an array or batch

        Args:
            script: Base job script
            array_spec: Array specification for Slurm
            commands: List of commands (not used for Slurm)
            job_name_prefix: Prefix for job names
            nodes: Nodes per job
            tasks_per_node: Tasks per node per job
            time_limit: Time limit per job
            max_concurrent: Maximum concurrent jobs

        Returns:
            Dict with batch submission results

        Raises:
            NotImplementedError: This method is not yet implemented for Slurm
        """
        raise NotImplementedError(
            "submit_batch is not yet implemented for Slurm adapter. "
            "Use MockAdapter with USE_MOCK_BACKENDS=true for testing."
        )

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
