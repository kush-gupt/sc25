"""Retrieve stdout and/or stderr from a job"""

import json
from typing import Annotated, Optional
from fastmcp.exceptions import ToolError
from core.app import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": True,  # Reading output is read-only
        "idempotentHint": True,  # Same query returns same result
        "openWorldHint": False,
    }
)
async def get_job_output(
    cluster: Annotated[str, "Cluster name from registry"],
    job_id: Annotated[str, "Job ID to retrieve output from"],
    output_type: Annotated[Optional[str], "Output type: stdout (default), stderr, or both"] = "stdout",
    tail_lines: Annotated[Optional[int], "Return only last N lines (default: all)"] = None,
) -> str:
    """Retrieve stdout and/or stderr from a job

    This tool retrieves the output (stdout and/or stderr) from a completed or running job
    on an HPC cluster. The backend is automatically selected based on cluster configuration.

    Args:
        cluster: Cluster name from registry
        job_id: Job ID to retrieve output from
        output_type: Output type: "stdout" (default), "stderr", or "both"
        tail_lines: Optional number of lines to return from end of output (default: all)

    Returns:
        JSON string containing:
        - success: bool indicating if output retrieval succeeded
        - job_id: string job ID
        - stdout: string stdout content (if output_type is "stdout" or "both")
        - stderr: string stderr content (if output_type is "stderr" or "both")
        - truncated: bool indicating if tail_lines was applied
        - error: string error message if failed

    Raises:
        ToolError: If validation fails or output cannot be retrieved
    """
    # Validate and normalize cluster name
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")
    cluster = cluster.strip()

    # Validate and normalize job_id
    if not job_id or not job_id.strip():
        raise ToolError("Job ID cannot be empty")
    job_id = job_id.strip()

    # Validate and normalize output_type
    if output_type is None:
        output_type = "stdout"
    output_type = output_type.strip().lower()

    valid_output_types = {"stdout", "stderr", "both"}
    if output_type not in valid_output_types:
        raise ToolError(
            f"Invalid output_type: {output_type}. "
            f"Must be one of: {', '.join(valid_output_types)}"
        )

    # Validate tail_lines if provided
    if tail_lines is not None and tail_lines < 1:
        raise ToolError(f"tail_lines must be >= 1, got {tail_lines}")

    # Get backend adapter from cluster registry
    from cluster_registry import get_registry

    try:
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # Get job output via backend adapter
        output_result = await adapter.get_job_output(
            job_id=job_id,
            output_type=output_type,
            tail_lines=tail_lines
        )

        return json.dumps(output_result, indent=2)

    except Exception as e:
        # Return error response
        result = {
            "success": False,
            "job_id": job_id,
            "error": str(e),
        }
        return json.dumps(result, indent=2)