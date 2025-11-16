"""Base adapter interface for HPC backends"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class JobSubmitParams:
    """Parameters for job submission"""

    script: str
    job_name: Optional[str] = None
    nodes: Optional[int] = None
    tasks_per_node: Optional[int] = None
    cpus_per_task: Optional[int] = None
    memory: Optional[str] = None
    time_limit: Optional[str] = None
    partition: Optional[str] = None
    output_path: Optional[str] = None
    error_path: Optional[str] = None
    working_dir: Optional[str] = None


@dataclass
class JobSubmitResult:
    """Result of job submission"""

    success: bool
    job_id: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None


@dataclass
class JobDetails:
    """Job information (supports both concise and detailed formats)"""

    job_id: str
    name: str
    state: str
    submitted: str  # ISO8601 timestamp
    runtime: str  # HH:MM:SS format
    exit_code: Optional[int] = None

    # Detailed format fields (optional)
    user: Optional[str] = None
    partition: Optional[str] = None
    started: Optional[str] = None  # ISO8601 timestamp
    ended: Optional[str] = None  # ISO8601 timestamp
    time_limit: Optional[str] = None  # HH:MM:SS format
    resources: Optional[Dict[str, Any]] = None
    allocated_nodes: Optional[List[str]] = None
    working_directory: Optional[str] = None
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None

    def to_concise_dict(self) -> Dict[str, Any]:
        """Return concise format dictionary"""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "state": self.state,
            "submitted": self.submitted,
            "runtime": self.runtime,
            "exit_code": self.exit_code,
        }

    def to_detailed_dict(self) -> Dict[str, Any]:
        """Return detailed format dictionary"""
        result = self.to_concise_dict()
        result.update(
            {
                "user": self.user,
                "partition": self.partition,
                "started": self.started,
                "ended": self.ended,
                "time_limit": self.time_limit,
                "resources": self.resources,
                "allocated_nodes": self.allocated_nodes,
                "working_directory": self.working_directory,
                "stdout_path": self.stdout_path,
                "stderr_path": self.stderr_path,
            }
        )
        return result


class BackendAdapter(ABC):
    """Abstract base class for HPC backend adapters"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration

        Args:
            config: Backend-specific configuration dict
        """
        self.config = config

    @abstractmethod
    async def submit_job(self, params: JobSubmitParams) -> JobSubmitResult:
        """
        Submit a job to the backend

        Args:
            params: Job submission parameters

        Returns:
            JobSubmitResult with job_id if successful

        Raises:
            Exception: If submission fails
        """
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> JobDetails:
        """
        Get information about a specific job

        Args:
            job_id: Job ID to query

        Returns:
            JobDetails with job information

        Raises:
            Exception: If job not found or query fails
        """
        pass

    @abstractmethod
    async def list_jobs(
        self,
        user: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobDetails]:
        """
        List jobs with optional filters

        Args:
            user: Optional username filter
            state: Optional state filter
            limit: Maximum number of jobs to return

        Returns:
            List of JobDetails

        Raises:
            Exception: If query fails
        """
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str, signal: str = "TERM") -> Dict[str, Any]:
        """
        Cancel a running or pending job

        Args:
            job_id: Job ID to cancel
            signal: Signal to send (TERM, KILL, INT)

        Returns:
            Dict with success status and message

        Raises:
            Exception: If cancellation fails
        """
        pass

    @abstractmethod
    async def get_job_output(
        self, job_id: str, output_type: str = "stdout", tail_lines: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve job output (stdout/stderr)

        Args:
            job_id: Job ID
            output_type: "stdout", "stderr", or "both"
            tail_lines: Optional number of lines from end

        Returns:
            Dict with stdout and/or stderr content

        Raises:
            Exception: If output unavailable
        """
        pass

    @abstractmethod
    async def get_queue_status(self, response_format: str = "concise") -> Dict[str, Any]:
        """
        Get queue statistics and utilization overview

        Args:
            response_format: "concise" (default) or "detailed"

        Returns:
            Dict with queue statistics:
                - concise: total_jobs, running, pending, completed
                - detailed: adds failed, cancelled, utilization, recent_jobs

        Raises:
            Exception: If query fails
        """
        pass

    @abstractmethod
    async def get_resources(self, response_format: str = "concise") -> Dict[str, Any]:
        """
        Get cluster resource availability and configuration

        Args:
            response_format: "concise" (default) or "detailed"

        Returns:
            Dict with resource information:
                - concise: nodes (total, idle, allocated, down),
                  cores (total, available)
                - detailed: adds partitions and node_details arrays

        Raises:
            Exception: If query fails
        """
        pass

    @abstractmethod
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
            Dict with accounting data:
                - success: bool
                - jobs: List of job records
                - total: Total matching jobs

            Concise format fields per job:
                - job_id, name, user, state, exit_code, runtime, cpu_time

            Detailed format adds:
                - memory_used_max, memory_requested, cpu_efficiency, wait_time,
                  nodes_used, submit_time, start_time, end_time

        Raises:
            Exception: If query fails
        """
        pass

    @abstractmethod
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
            script: Base job script (may include array task variable)
            array_spec: Array specification for Slurm (e.g., "1-10", "1-100:2")
            commands: List of commands for Flux bulk submission
            job_name_prefix: Prefix for job names
            nodes: Nodes per job
            tasks_per_node: Tasks per node per job
            time_limit: Time limit per job
            max_concurrent: Maximum concurrent jobs (Slurm arrays only)

        Returns:
            Dict with batch submission results:
                - success: bool
                - job_ids: List[str]
                - batch_type: "array" or "bulk"
                - submitted: int
                - failed: int
                - errors: List[Dict] with index, command, error

        Raises:
            Exception: If submission fails
        """
        pass

    async def close(self):
        """
        Close connections and cleanup resources
        Override in subclasses if needed
        """
        pass
