"""Mock backend adapter for testing without real HPC clusters"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from .base import (
    BackendAdapter,
    JobSubmitParams,
    JobSubmitResult,
    JobDetails,
)


class MockAdapter(BackendAdapter):
    """Mock backend adapter that simulates HPC job management"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize mock adapter

        Args:
            config: Configuration dict (can include mock_type: 'slurm' or 'flux')
        """
        super().__init__(config)
        self.mock_type = config.get("mock_type", "slurm")
        self.jobs: Dict[str, JobDetails] = {}
        self.job_counter = 1000

    def _generate_job_id(self) -> str:
        """Generate a mock job ID"""
        job_id = str(self.job_counter)
        self.job_counter += 1

        # Format based on backend type
        if self.mock_type == "flux":
            # Flux uses format like ƒAbCd12
            return f"ƒ{job_id}"
        else:
            # Slurm uses numeric IDs
            return job_id

    def _create_mock_job(
        self, job_id: str, params: JobSubmitParams, state: str = "PENDING"
    ) -> JobDetails:
        """Create a mock job with realistic data"""
        now = datetime.now(timezone.utc)
        # Format timestamps with 'Z' suffix for UTC (ISO8601)
        submitted = now.isoformat().replace("+00:00", "Z")

        # Simulate some jobs starting
        started = None
        runtime = "00:00:00"
        if state in ["RUNNING", "COMPLETED"]:
            started = now.isoformat().replace("+00:00", "Z")
            runtime = "00:15:23"

        # Create job details
        job = JobDetails(
            job_id=job_id,
            name=params.job_name or "mock-job",
            state=state,
            submitted=submitted,
            runtime=runtime,
            exit_code=0 if state == "COMPLETED" else None,
            user=self.config.get("user", "mock-user"),
            partition=params.partition or "default",
            started=started,
            ended=now.isoformat().replace("+00:00", "Z") if state == "COMPLETED" else None,
            time_limit=params.time_limit or "01:00:00",
            resources={
                "nodes": params.nodes or 1,
                "tasks": params.tasks_per_node or 1,
                "cpus_per_task": params.cpus_per_task or 1,
                "memory": params.memory or "4GB",
            },
            allocated_nodes=[f"node-{i:02d}" for i in range(1, (params.nodes or 1) + 1)],
            working_directory=params.working_dir or "/tmp",
            stdout_path=params.output_path or f"/tmp/job-{job_id}.out",
            stderr_path=params.error_path or f"/tmp/job-{job_id}.err",
        )

        return job

    async def submit_job(self, params: JobSubmitParams) -> JobSubmitResult:
        """Submit a mock job"""
        try:
            # Simulate job submission
            job_id = self._generate_job_id()

            # Create mock job in PENDING state
            job = self._create_mock_job(job_id, params, state="PENDING")
            self.jobs[job_id] = job

            return JobSubmitResult(
                success=True,
                job_id=job_id,
                state="PENDING",
            )

        except Exception as e:
            return JobSubmitResult(success=False, error=str(e))

    async def get_job(self, job_id: str) -> JobDetails:
        """Get mock job information"""
        if job_id not in self.jobs:
            # Create a mock job on the fly if it doesn't exist
            # This allows testing with arbitrary job IDs
            mock_params = JobSubmitParams(
                script="#!/bin/bash\necho 'mock job'",
                job_name="mock-job",
            )
            job = self._create_mock_job(job_id, mock_params, state="RUNNING")
            self.jobs[job_id] = job

        return self.jobs[job_id]

    async def list_jobs(
        self,
        user: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobDetails]:
        """List mock jobs"""
        # Create some mock jobs if none exist
        if not self.jobs:
            for i in range(5):
                job_id = self._generate_job_id()
                mock_params = JobSubmitParams(
                    script="#!/bin/bash\necho 'test'",
                    job_name=f"mock-job-{i}",
                )
                states = ["PENDING", "RUNNING", "COMPLETED", "FAILED"]
                job_state = states[i % len(states)]
                self.jobs[job_id] = self._create_mock_job(
                    job_id, mock_params, state=job_state
                )

        # Apply filters
        result = []
        for job in self.jobs.values():
            if user and job.user != user:
                continue
            if state and job.state != state:
                continue
            result.append(job)

        # Sort by job_id (most recent first) and apply limit
        result.sort(key=lambda j: j.job_id, reverse=True)
        return result[:limit]

    async def cancel_job(self, job_id: str, signal: str = "TERM") -> Dict[str, Any]:
        """Cancel a mock job"""
        try:
            if job_id in self.jobs:
                self.jobs[job_id].state = "CANCELLED"

            return {
                "success": True,
                "job_id": job_id,
                "state": "CANCELLED",
                "message": f"Mock job {job_id} cancelled",
            }

        except Exception as e:
            return {"success": False, "job_id": job_id, "error": str(e)}

    async def get_job_output(
        self, job_id: str, output_type: str = "stdout", tail_lines: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get mock job output"""
        # Generate mock output
        mock_stdout = f"Mock job {job_id} output\nLine 2\nLine 3\nCompleted successfully"
        mock_stderr = ""

        result = {
            "success": True,
            "job_id": job_id,
        }

        if output_type in ["stdout", "both"]:
            if tail_lines:
                lines = mock_stdout.split("\n")
                result["stdout"] = "\n".join(lines[-tail_lines:])
                result["truncated"] = len(lines) > tail_lines
            else:
                result["stdout"] = mock_stdout
                result["truncated"] = False

        if output_type in ["stderr", "both"]:
            result["stderr"] = mock_stderr

        return result

    async def get_queue_status(self, response_format: str = "concise") -> Dict[str, Any]:
        """Get queue statistics and utilization overview"""
        # Ensure we have some mock jobs
        if not self.jobs:
            # Create initial mock jobs
            await self.list_jobs()

        # Count jobs by state
        state_counts = {
            "PENDING": 0,
            "RUNNING": 0,
            "COMPLETED": 0,
            "FAILED": 0,
            "CANCELLED": 0,
        }

        for job in self.jobs.values():
            state = job.state
            if state in state_counts:
                state_counts[state] += 1

        total_jobs = len(self.jobs)

        # Build concise response
        result = {
            "success": True,
            "cluster": self.config.get("name", "mock-cluster"),
            "total_jobs": total_jobs,
            "running": state_counts["RUNNING"],
            "pending": state_counts["PENDING"],
            "completed": state_counts["COMPLETED"],
        }

        # Add detailed fields if requested
        if response_format == "detailed":
            # Calculate mock utilization metrics
            nodes_total = 32
            cores_total = 128
            nodes_allocated = min(state_counts["RUNNING"] * 2, nodes_total)
            cores_allocated = min(state_counts["RUNNING"] * 8, cores_total)

            result["failed"] = state_counts["FAILED"]
            result["cancelled"] = state_counts["CANCELLED"]
            result["utilization"] = {
                "nodes_allocated": nodes_allocated,
                "nodes_total": nodes_total,
                "cores_allocated": cores_allocated,
                "cores_total": cores_total,
            }

            # Get recent jobs (up to 20 most recent)
            recent = sorted(self.jobs.values(), key=lambda j: j.job_id, reverse=True)[:20]
            result["recent_jobs"] = [
                {
                    "job_id": job.job_id,
                    "name": job.name,
                    "state": job.state,
                    "runtime": job.runtime,
                }
                for job in recent
            ]

        return result

    async def get_accounting(
        self,
        job_id: Optional[str] = None,
        user: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        response_format: str = "concise",
    ) -> Dict[str, Any]:
        """Get historical job accounting and performance data"""
        # Ensure we have some mock jobs
        if not self.jobs:
            await self.list_jobs()

        # Filter jobs based on criteria
        matching_jobs = []
        for job in self.jobs.values():
            # Filter by job_id
            if job_id and job.job_id != job_id:
                continue

            # Filter by user
            if user and job.user != user:
                continue

            # Time range filtering (simplified for mock)
            # In real implementation, would parse ISO8601 and compare
            if start_time or end_time:
                # For mock, just include jobs if time filters are present
                pass

            matching_jobs.append(job)

        # Sort by job_id (most recent first) and apply limit
        matching_jobs.sort(key=lambda j: j.job_id, reverse=True)
        total = len(matching_jobs)
        matching_jobs = matching_jobs[:limit]

        # Build response based on format
        jobs_data = []
        for job in matching_jobs:
            # Calculate mock CPU time (simulate as 80% of runtime)
            runtime_parts = job.runtime.split(":")
            if len(runtime_parts) == 3:
                hours = int(runtime_parts[0])
                minutes = int(runtime_parts[1])
                seconds = int(runtime_parts[2])
                total_seconds = hours * 3600 + minutes * 60 + seconds
                cpu_seconds = int(total_seconds * 0.8)
                cpu_hours = cpu_seconds // 3600
                cpu_minutes = (cpu_seconds % 3600) // 60
                cpu_secs = cpu_seconds % 60
                cpu_time = f"{cpu_hours:02d}:{cpu_minutes:02d}:{cpu_secs:02d}"
            else:
                cpu_time = job.runtime

            job_record = {
                "job_id": job.job_id,
                "name": job.name,
                "user": job.user or "mock-user",
                "state": job.state,
                "exit_code": job.exit_code or 0,
                "runtime": job.runtime,
                "cpu_time": cpu_time,
            }

            # Add detailed fields if requested
            if response_format == "detailed":
                # Calculate mock wait time (time between submit and start)
                wait_time = "00:05:23"  # Mock 5 minutes wait

                # Mock memory values
                memory_requested = job.resources.get("memory", "4GB") if job.resources else "4GB"
                memory_used_max = "3.2GB"  # Mock usage

                # Mock CPU efficiency
                cpu_efficiency = 0.85  # 85% efficiency

                job_record.update(
                    {
                        "memory_used_max": memory_used_max,
                        "memory_requested": memory_requested,
                        "cpu_efficiency": cpu_efficiency,
                        "wait_time": wait_time,
                        "nodes_used": job.allocated_nodes or ["node-01"],
                        "submit_time": job.submitted,
                        "start_time": job.started or job.submitted,
                        "end_time": job.ended or job.submitted,
                    }
                )

            jobs_data.append(job_record)

        return {"success": True, "jobs": jobs_data, "total": total}

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
        """Submit multiple jobs as an array or batch"""
        job_ids = []
        submitted = 0
        failed = 0
        errors = []

        # Determine batch type
        if array_spec:
            batch_type = "array"
            # Parse array spec (e.g., "1-10" or "1-100:2")
            try:
                if "-" in array_spec:
                    parts = array_spec.split("-")
                    start = int(parts[0])
                    end_step = parts[1]
                    if ":" in end_step:
                        end, step = end_step.split(":")
                        end = int(end)
                        step = int(step)
                    else:
                        end = int(end_step)
                        step = 1

                    count = 0
                    for i in range(start, end + 1, step):
                        if max_concurrent and count >= max_concurrent:
                            break
                        job_id = self._generate_job_id()
                        job_ids.append(job_id)
                        submitted += 1
                        count += 1
            except Exception as e:
                errors.append({"index": 0, "command": array_spec, "error": str(e)})
                failed += 1

        elif commands:
            batch_type = "bulk"
            # Submit each command as a separate job
            for idx, cmd in enumerate(commands):
                try:
                    job_id = self._generate_job_id()
                    job_ids.append(job_id)
                    submitted += 1
                except Exception as e:
                    errors.append({"index": idx, "command": cmd, "error": str(e)})
                    failed += 1
        else:
            return {
                "success": False,
                "error": "Either array_spec or commands must be provided",
            }

        return {
            "success": submitted > 0,
            "job_ids": job_ids,
            "batch_type": batch_type,
            "submitted": submitted,
            "failed": failed,
            "errors": errors,
        }

    async def get_resources(self, response_format: str = "concise") -> Dict[str, Any]:
        """Get cluster resource availability and configuration"""
        # Mock cluster resource data
        nodes_total = 32
        cores_per_node = 4
        cores_total = nodes_total * cores_per_node

        # Calculate nodes in different states based on running jobs
        # Ensure we have some mock jobs to base calculations on
        if not self.jobs:
            await self.list_jobs()

        running_jobs = sum(1 for job in self.jobs.values() if job.state == "RUNNING")
        nodes_allocated = min(running_jobs * 2, nodes_total - 4)  # Leave some down
        nodes_down = 2
        nodes_idle = nodes_total - nodes_allocated - nodes_down

        cores_allocated = nodes_allocated * cores_per_node
        cores_available = cores_total - cores_allocated - (nodes_down * cores_per_node)

        # Build concise response
        result = {
            "success": True,
            "nodes": {
                "total": nodes_total,
                "idle": nodes_idle,
                "allocated": nodes_allocated,
                "down": nodes_down,
            },
            "cores": {
                "total": cores_total,
                "available": cores_available,
            },
        }

        # Add detailed fields if requested
        if response_format == "detailed":
            # Generate mock partition information
            if self.mock_type == "slurm":
                result["partitions"] = [
                    {
                        "name": "default",
                        "state": "UP",
                        "nodes": 20,
                        "max_time_limit": "24:00:00",
                        "default_memory_per_cpu": "4GB",
                    },
                    {
                        "name": "gpu",
                        "state": "UP",
                        "nodes": 8,
                        "max_time_limit": "12:00:00",
                        "default_memory_per_cpu": "8GB",
                    },
                    {
                        "name": "debug",
                        "state": "UP",
                        "nodes": 4,
                        "max_time_limit": "01:00:00",
                        "default_memory_per_cpu": "2GB",
                    },
                ]
            else:
                # Flux uses a flat structure, simulate with mock partitions
                result["partitions"] = [
                    {
                        "name": "batch",
                        "state": "UP",
                        "nodes": 28,
                        "max_time_limit": "24:00:00",
                        "default_memory_per_cpu": "4GB",
                    },
                    {
                        "name": "debug",
                        "state": "UP",
                        "nodes": 4,
                        "max_time_limit": "01:00:00",
                        "default_memory_per_cpu": "2GB",
                    },
                ]

            # Generate mock node details
            node_details = []
            for i in range(nodes_total):
                node_num = i + 1
                # Determine node state
                if i < nodes_idle:
                    state = "IDLE"
                    partitions = ["default", "debug"]
                elif i < nodes_idle + nodes_allocated:
                    state = "ALLOCATED"
                    partitions = ["default", "gpu"]
                else:
                    state = "DOWN"
                    partitions = ["default"]

                node_details.append({
                    "name": f"node-{node_num:02d}",
                    "state": state,
                    "cpus": cores_per_node,
                    "memory": "16GB",
                    "partitions": partitions,
                })

            result["node_details"] = node_details

        return result

    async def close(self):
        """Cleanup (nothing to do for mock adapter)"""
        pass
