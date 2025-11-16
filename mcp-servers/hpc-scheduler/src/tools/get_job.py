"""Get information about a specific job"""

import json
from typing import Annotated, Optional
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": True,  # This is a read operation
        "idempotentHint": True,  # Multiple calls return same result
        "openWorldHint": False,
    }
)
async def get_job(
    cluster: Annotated[str, Field(description="Cluster name")],
    job_id: Annotated[str, Field(description="Job ID to query")],
    response_format: Annotated[
        str, Field(description='Response format: "concise" (default) or "detailed"')
    ] = "concise",
) -> str:
    """Get information about a specific job

    Retrieves job information from the specified HPC cluster with either
    concise or detailed response format.

    Args:
        cluster: Cluster name
        job_id: Job ID to query
        response_format: Response format - "concise" (default) or "detailed"

    Returns:
        JSON string containing job information. Format depends on response_format:

        Concise format includes:
        - job_id: Job identifier
        - name: Job name
        - state: Job state (PENDING|RUNNING|COMPLETED|FAILED|CANCELLED)
        - submitted: Submission timestamp (ISO8601)
        - runtime: Runtime duration (HH:MM:SS)
        - exit_code: Exit code (integer or null)

        Detailed format includes all concise fields plus:
        - user: Username
        - partition: Partition/queue name
        - started: Start timestamp (ISO8601)
        - ended: End timestamp (ISO8601)
        - time_limit: Time limit (HH:MM:SS)
        - resources: Resource allocation details
        - allocated_nodes: List of node names
        - working_directory: Working directory path
        - stdout_path: Standard output file path
        - stderr_path: Standard error file path

    Raises:
        ToolError: If validation fails or job cannot be retrieved
    """
    # Validate and normalize cluster name
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")
    cluster = cluster.strip()

    # Validate and normalize job_id
    if not job_id or not job_id.strip():
        raise ToolError("Job ID cannot be empty")
    job_id = job_id.strip()

    # Validate and normalize response_format
    response_format = response_format.strip().lower()
    if response_format not in ["concise", "detailed"]:
        raise ToolError(
            f"Invalid response_format: '{response_format}'. "
            'Must be "concise" or "detailed"'
        )

    # Get backend adapter from cluster registry
    from cluster_registry import get_registry

    try:
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # Get job details from backend
        job_details = await adapter.get_job(job_id)

        # Format response based on response_format
        if response_format == "concise":
            job_data = job_details.to_concise_dict()
        else:  # detailed
            job_data = job_details.to_detailed_dict()

        result = {"success": True, "job": job_data}

        return json.dumps(result, indent=2)

    except Exception as e:
        # Return error response
        result = {
            "success": False,
            "job_id": job_id,
            "error": str(e),
        }
        return json.dumps(result, indent=2)