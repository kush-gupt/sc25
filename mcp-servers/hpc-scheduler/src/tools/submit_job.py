"""Submit a batch job to an HPC cluster"""

import json
from typing import Annotated, Optional
from fastmcp.exceptions import ToolError
from core.app import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": False,  # This creates a job, not read-only
        "idempotentHint": False,  # Submitting the same job multiple times creates multiple jobs
        "openWorldHint": False,
    }
)
async def submit_job(
    cluster: Annotated[str, "Cluster name from registry"],
    script: Annotated[str, "Job script content including shebang (e.g., #!/bin/bash)"],
    job_name: Annotated[Optional[str], "Name for the job"] = None,
    nodes: Annotated[Optional[int], "Number of nodes to request"] = None,
    tasks_per_node: Annotated[Optional[int], "Number of tasks per node"] = None,
    cpus_per_task: Annotated[Optional[int], "CPUs per task"] = None,
    memory: Annotated[Optional[str], "Memory per node (e.g., 32GB, 1024MB)"] = None,
    time_limit: Annotated[Optional[str], "Time limit (e.g., 1h, 30m, 2:00:00)"] = None,
    partition: Annotated[Optional[str], "Partition/queue to submit to (Slurm only)"] = None,
    output_path: Annotated[Optional[str], "Path for stdout output"] = None,
    error_path: Annotated[Optional[str], "Path for stderr output"] = None,
    working_dir: Annotated[Optional[str], "Working directory for the job"] = None,
) -> str:
    """Submit a batch job to an HPC cluster

    This tool submits a batch job to a configured HPC cluster (Slurm or Flux).
    The backend is automatically selected based on cluster configuration.

    Args:
        cluster: Cluster name from registry
        script: Job script content including shebang (e.g., #!/bin/bash)
        job_name: Optional name for the job
        nodes: Optional number of nodes to request
        tasks_per_node: Optional number of tasks per node
        cpus_per_task: Optional CPUs per task
        memory: Optional memory per node (e.g., 32GB, 1024MB)
        time_limit: Optional time limit (e.g., 1h, 30m, 2:00:00)
        partition: Optional partition/queue to submit to (Slurm only)
        output_path: Optional path for stdout output
        error_path: Optional path for stderr output
        working_dir: Optional working directory for the job (defaults to /tmp if not specified)

    Returns:
        JSON string containing:
        - success: bool indicating if submission succeeded
        - job_id: string job ID if successful
        - cluster: string cluster name
        - backend: string backend type (slurm or flux)
        - state: string job state (PENDING or SUBMITTED)
        - error: string error message if failed

    Raises:
        ToolError: If validation fails or submission cannot be completed
    """
    # Validate and normalize cluster name
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")
    cluster = cluster.strip()

    # Validate and normalize script
    if not script or not script.strip():
        raise ToolError("Script cannot be empty")
    script = script.strip()

    # Validate script has shebang
    script_lines = script.strip().split('\n')
    if not script_lines[0].startswith('#!'):
        raise ToolError(
            "Script must include shebang line (e.g., #!/bin/bash). "
            f"First line was: {script_lines[0]}"
        )

    # Validate numeric parameters if provided
    if nodes is not None and nodes < 1:
        raise ToolError(f"Number of nodes must be >= 1, got {nodes}")

    if tasks_per_node is not None and tasks_per_node < 1:
        raise ToolError(f"Tasks per node must be >= 1, got {tasks_per_node}")

    if cpus_per_task is not None and cpus_per_task < 1:
        raise ToolError(f"CPUs per task must be >= 1, got {cpus_per_task}")

    # Validate memory format if provided
    if memory is not None:
        memory = memory.strip()
        if not memory:
            raise ToolError("Memory parameter cannot be empty string")
        # Check for valid memory format (number followed by unit)
        import re
        if not re.match(r'^\d+\s*(MB|GB|TB|M|G|T)$', memory, re.IGNORECASE):
            raise ToolError(
                f"Invalid memory format: {memory}. "
                "Expected format: <number><unit> (e.g., 32GB, 1024MB)"
            )

    # Validate time_limit format if provided
    if time_limit is not None:
        time_limit = time_limit.strip()
        if not time_limit:
            raise ToolError("Time limit parameter cannot be empty string")
        # Check for valid time formats: 1h, 30m, 2:00:00, etc.
        import re
        valid_formats = [
            r'^\d+[hms]$',  # 1h, 30m, 60s
            r'^\d+:\d+$',  # 1:30 (minutes:seconds)
            r'^\d+:\d+:\d+$',  # 1:30:00 (hours:minutes:seconds)
        ]
        if not any(re.match(pattern, time_limit, re.IGNORECASE) for pattern in valid_formats):
            raise ToolError(
                f"Invalid time limit format: {time_limit}. "
                "Expected formats: 1h, 30m, 60s, 1:30, or 1:30:00"
            )

    # Set default working directory if not provided
    if working_dir is None:
        working_dir = "/tmp"

    # Get backend adapter from cluster registry
    from cluster_registry import get_registry
    from backends.base import JobSubmitParams

    try:
        registry = get_registry()
        adapter = registry.get_adapter(cluster)
        cluster_info = registry.get_cluster_info(cluster)
        backend_type = cluster_info.get("type", "unknown")

        # Create job submission parameters
        params = JobSubmitParams(
            script=script,
            job_name=job_name,
            nodes=nodes,
            tasks_per_node=tasks_per_node,
            cpus_per_task=cpus_per_task,
            memory=memory,
            time_limit=time_limit,
            partition=partition,
            output_path=output_path,
            error_path=error_path,
            working_dir=working_dir,
        )

        # Submit job via backend adapter
        submit_result = await adapter.submit_job(params)

        # Build response
        result = {
            "success": submit_result.success,
            "cluster": cluster,
            "backend": backend_type,
        }

        if submit_result.success:
            result["job_id"] = submit_result.job_id
            result["state"] = submit_result.state
        else:
            result["error"] = submit_result.error

        return json.dumps(result, indent=2)

    except Exception as e:
        # Return error response
        result = {
            "success": False,
            "cluster": cluster,
            "error": str(e),
        }
        return json.dumps(result, indent=2)