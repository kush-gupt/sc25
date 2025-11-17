"""Flux backend adapter using Kubernetes exec"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from .base import (
    BackendAdapter,
    JobSubmitParams,
    JobSubmitResult,
    JobDetails,
)


class FluxAdapter(BackendAdapter):
    """Flux backend adapter using Kubernetes exec to run flux CLI commands"""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize Flux adapter

        Args:
            config_dict: Configuration dict with:
                - namespace: Kubernetes namespace for Flux minicluster
                - minicluster: Name of Flux minicluster
                - flux_uri: Flux URI (e.g., local:///mnt/flux/view/run/flux/local)
                - container: Container name (default: flux-sample)
        """
        super().__init__(config_dict)
        self.namespace = config_dict["namespace"]
        self.minicluster = config_dict["minicluster"]
        self.flux_uri = config_dict.get(
            "flux_uri", "local:///mnt/flux/config/run/flux/local"
        )
        self.container = config_dict.get("container", "flux-sample")

        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.v1 = client.CoreV1Api()

    async def _get_flux_pod(self) -> str:
        """
        Get the first Flux pod name for the minicluster

        Returns:
            Pod name

        Raises:
            Exception: If no pods found
        """
        try:
            label_selector = f"job-name={self.minicluster}"
            pods = self.v1.list_namespaced_pod(
                namespace=self.namespace, label_selector=label_selector
            )

            if not pods.items:
                raise Exception(
                    f"No Flux pods found with label job-name={self.minicluster}"
                )

            # Return first ready pod
            for pod in pods.items:
                if pod.status.phase == "Running":
                    return pod.metadata.name

            # If no running pod, return first pod
            return pods.items[0].metadata.name

        except ApiException as e:
            raise Exception(f"Failed to get Flux pods: {e}")

    async def _exec_flux_command(self, command: List[str], stdin_data: Optional[str] = None) -> str:
        """
        Execute a flux command in the Flux pod

        Args:
            command: Command to execute (e.g., ["flux", "jobs"])
            stdin_data: Optional data to pass via stdin

        Returns:
            Command output as string

        Raises:
            Exception: If command fails
        """
        pod_name = await self._get_flux_pod()

        # Build command array safely without shell injection
        # Set FLUX_URI via env and execute command directly
        full_command = ["sh", "-c", f'export FLUX_URI="{self.flux_uri}"; exec "$@"', "--"] + command

        try:
            # Execute command using kubernetes stream
            resp = stream(
                self.v1.connect_get_namespaced_pod_exec,
                pod_name,
                self.namespace,
                container=self.container,
                command=full_command,
                stderr=True,
                stdin=bool(stdin_data),
                stdout=True,
                tty=False,
                _preload_content=False if stdin_data else True,
            )

            # If we have stdin data, write it and read response
            if stdin_data:
                resp.write_stdin(stdin_data)
                resp.close()
                output = ""
                while resp.is_open():
                    if resp.peek_stdout():
                        output += resp.read_stdout()
                    if resp.peek_stderr():
                        # Collect stderr for error reporting
                        pass
                return output
            else:
                return resp

        except ApiException as e:
            raise Exception(f"Failed to exec command in pod {pod_name}: {e}")

    def _normalize_state(self, flux_state: str) -> str:
        """Normalize Flux job state to unified format"""
        state_map = {
            "DEPEND": "PENDING",
            "SCHED": "PENDING",
            "RUN": "RUNNING",
            "INACTIVE": "COMPLETED",  # Need to check result_code
            "CANCELED": "CANCELLED",
            "TIMEOUT": "TIMEOUT",
        }
        return state_map.get(flux_state, flux_state)

    def _parse_flux_duration(self, duration_str: str) -> str:
        """
        Convert Flux duration to HH:MM:SS format

        Args:
            duration_str: Duration string (e.g., "1.5h", "90m", "30s")

        Returns:
            HH:MM:SS formatted string
        """
        if not duration_str or duration_str == "-":
            return "00:00:00"

        # Parse duration string
        match = re.match(r"([\d.]+)([smhd]?)", duration_str)
        if not match:
            return "00:00:00"

        value = float(match.group(1))
        unit = match.group(2) or "s"

        # Convert to seconds
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        total_seconds = int(value * multipliers.get(unit, 1))

        # Convert to HH:MM:SS
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    async def submit_job(self, params: JobSubmitParams) -> JobSubmitResult:
        """Submit a job to Flux via flux run command"""
        try:
            # Build flux submit command
            cmd = ["flux", "submit"]

            if params.job_name:
                cmd.extend(["--setattr", f"user.name={params.job_name}"])
            if params.nodes:
                cmd.extend(["-N", str(params.nodes)])
            if params.tasks_per_node:
                cmd.extend(["-n", str(params.tasks_per_node)])
            if params.cpus_per_task:
                cmd.extend(["-c", str(params.cpus_per_task)])
            if params.time_limit:
                cmd.extend(["-t", params.time_limit])
            if params.output_path:
                cmd.extend(["-o", params.output_path])
            if params.error_path:
                cmd.extend(["-e", params.error_path])

            # Add working directory (flux uses --cwd)
            working_dir = params.working_dir or "/tmp"
            cmd.extend(["--cwd", working_dir])

            # Use '-' to tell flux submit to read script from stdin
            cmd.append("-")

            # Execute submission, passing script via stdin
            output = await self._exec_flux_command(cmd, stdin_data=params.script)

            # Flux returns job ID on success (format: ƒAbCd12)
            job_id = output.strip()
            if not job_id:
                return JobSubmitResult(success=False, error="No job ID returned")

            return JobSubmitResult(success=True, job_id=job_id, state="PENDING")

        except Exception as e:
            return JobSubmitResult(success=False, error=str(e))

    async def get_job(self, job_id: str) -> JobDetails:
        """Get job information from Flux"""
        try:
            # Use flux jobs with JSON output for detailed info
            output = await self._exec_flux_command(
                ["flux", "jobs", "-o", "{id},{name},{state},{t_submit},{t_run},{t_inactive},{result},{nnodes},{ntasks},{duration},{runtime}", "--filter", f"id={job_id}"]
            )

            if not output.strip():
                raise Exception(f"Job {job_id} not found")

            # Parse output (CSV-like format)
            fields = output.strip().split(",")
            if len(fields) < 11:
                raise Exception(f"Invalid job data for {job_id}")

            job_id_actual = fields[0]
            name = fields[1] or "unnamed"
            state = fields[2]
            t_submit = fields[3]
            t_run = fields[4]
            t_inactive = fields[5]
            result = fields[6]
            nnodes = fields[7]
            ntasks = fields[8]
            duration = fields[9]
            runtime = fields[10]

            # Determine exit code from result
            exit_code = None
            if result and result != "-":
                if result == "COMPLETED":
                    exit_code = 0
                elif result == "FAILED":
                    exit_code = 1
                elif result == "CANCELED":
                    exit_code = None

            # Format timestamps
            submitted = (
                datetime.fromtimestamp(float(t_submit), tz=timezone.utc).isoformat()
                if t_submit != "-"
                else ""
            )
            started = (
                datetime.fromtimestamp(float(t_run), tz=timezone.utc).isoformat()
                if t_run != "-"
                else None
            )
            ended = (
                datetime.fromtimestamp(float(t_inactive), tz=timezone.utc).isoformat()
                if t_inactive != "-"
                else None
            )

            # Build JobDetails
            details = JobDetails(
                job_id=job_id_actual,
                name=name,
                state=self._normalize_state(state),
                submitted=submitted,
                runtime=self._parse_flux_duration(runtime),
                exit_code=exit_code,
                user="flux",
                partition="default",
                started=started,
                ended=ended,
                time_limit=self._parse_flux_duration(duration),
                resources={
                    "nodes": int(nnodes) if nnodes.isdigit() else 0,
                    "tasks": int(ntasks) if ntasks.isdigit() else 0,
                    "cpus_per_task": 1,
                    "memory": "N/A",
                },
                allocated_nodes=[],
                working_directory="/tmp",
                stdout_path="",
                stderr_path="",
            )

            return details

        except Exception as e:
            raise Exception(f"Failed to get job {job_id}: {e}")

    async def list_jobs(
        self,
        user: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobDetails]:
        """List jobs from Flux"""
        try:
            # Build filter
            filter_args = []
            if state:
                # Map unified state to Flux state
                flux_state_map = {
                    "PENDING": "DEPEND,SCHED",
                    "RUNNING": "RUN",
                    "COMPLETED": "INACTIVE",
                    "FAILED": "INACTIVE",
                    "CANCELLED": "CANCELED",
                }
                flux_states = flux_state_map.get(state, state)
                filter_args = ["--filter", f"state={flux_states}"]

            # Get job list
            cmd = ["flux", "jobs", "-a", "-o", "{id},{name},{state},{t_submit},{runtime}"]
            if filter_args:
                cmd.extend(filter_args)

            output = await self._exec_flux_command(cmd)

            result = []
            for line in output.strip().split("\n"):
                if not line:
                    continue

                try:
                    fields = line.split(",")
                    if len(fields) < 5:
                        continue

                    job_id = fields[0]
                    name = fields[1] or "unnamed"
                    job_state = fields[2]
                    t_submit = fields[3]
                    runtime = fields[4]

                    # Format timestamp
                    submitted = (
                        datetime.fromtimestamp(
                            float(t_submit), tz=timezone.utc
                        ).isoformat()
                        if t_submit != "-"
                        else ""
                    )

                    details = JobDetails(
                        job_id=job_id,
                        name=name,
                        state=self._normalize_state(job_state),
                        submitted=submitted,
                        runtime=self._parse_flux_duration(runtime),
                        exit_code=None,
                    )
                    result.append(details)

                    if len(result) >= limit:
                        break

                except Exception:
                    continue

            return result

        except Exception as e:
            raise Exception(f"Failed to list jobs: {e}")

    async def cancel_job(self, job_id: str, signal: str = "TERM") -> Dict[str, Any]:
        """Cancel a job in Flux"""
        try:
            # Use flux cancel command
            signal_map = {"TERM": "SIGTERM", "KILL": "SIGKILL", "INT": "SIGINT"}
            flux_signal = signal_map.get(signal, "SIGTERM")

            await self._exec_flux_command(
                ["flux", "cancel", "--signal", flux_signal, job_id]
            )

            return {
                "success": True,
                "job_id": job_id,
                "state": "CANCELLED",
                "message": f"Job {job_id} cancelled with {flux_signal}",
            }

        except Exception as e:
            return {"success": False, "job_id": job_id, "error": str(e)}

    async def get_job_output(
        self, job_id: str, output_type: str = "stdout", tail_lines: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve job output from Flux using flux job attach

        Args:
            job_id: Flux job ID
            output_type: "stdout", "stderr", or "both"
            tail_lines: Optional number of lines from end

        Returns:
            Dict with stdout and/or stderr content
        """
        try:
            result = {"success": True, "job_id": job_id}

            if output_type in ["stdout", "both"]:
                cmd = ["flux", "job", "attach", job_id]
                stdout = await self._exec_flux_command(cmd)
                result["stdout"] = stdout

            if output_type in ["stderr", "both"]:
                # Flux stderr is part of attach output, would need log parsing
                result["stderr"] = ""

            if tail_lines:
                if "stdout" in result:
                    lines = result["stdout"].split("\n")
                    result["stdout"] = "\n".join(lines[-tail_lines:])
                result["truncated"] = True
            else:
                result["truncated"] = False

            return result

        except Exception as e:
            return {"success": False, "job_id": job_id, "error": str(e)}

    async def get_queue_status(self, response_format: str = "concise") -> Dict[str, Any]:
        """
        Get queue statistics and utilization overview

        Args:
            response_format: "concise" (default) or "detailed"

        Returns:
            Dict with queue statistics

        Raises:
            NotImplementedError: This method is not yet implemented for Flux
        """
        raise NotImplementedError(
            "get_queue_status is not yet implemented for Flux adapter. "
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
            NotImplementedError: This method is not yet implemented for Flux
        """
        raise NotImplementedError(
            "get_resources is not yet implemented for Flux adapter. "
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
            NotImplementedError: This method is not yet implemented for Flux
        """
        raise NotImplementedError(
            "get_accounting is not yet implemented for Flux adapter. "
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
            array_spec: Array specification (not used for Flux)
            commands: List of commands for Flux bulk submission
            job_name_prefix: Prefix for job names
            nodes: Nodes per job
            tasks_per_node: Tasks per node per job
            time_limit: Time limit per job
            max_concurrent: Maximum concurrent jobs (not enforced by Flux)

        Returns:
            Dict with batch submission results

        Raises:
            NotImplementedError: This method is not yet implemented for Flux
        """
        raise NotImplementedError(
            "submit_batch is not yet implemented for Flux adapter. "
            "Use MockAdapter with USE_MOCK_BACKENDS=true for testing."
        )

    async def close(self):
        """Cleanup (no persistent connections for k8s client)"""
        pass
