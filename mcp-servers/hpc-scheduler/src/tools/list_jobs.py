"""List jobs on a cluster with optional filters"""

from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def list_jobs(
    cluster: Annotated[str, Field(description="Cluster name")],
    user: Annotated[str | None, Field(description="Filter by username")] = None,
    state: Annotated[str | None, Field(description="Filter by state (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)")] = None,
    limit: Annotated[int, Field(description="Maximum number of jobs to return")] = 100,
    response_format: Annotated[str, Field(description="Response format: concise (default) or detailed")] = "concise",
) -> str:
    """List jobs on a cluster with optional filters

    Retrieves a list of jobs from the specified HPC cluster with optional
    filtering by user and/or state. Returns most recent jobs first.

    Args:
        cluster: Cluster name
        user: Optional filter by username
        state: Optional filter by state (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
        limit: Maximum number of jobs to return (default: 100)
        response_format: Response format: "concise" (default) or "detailed"

    Returns:
        JSON string containing:
        - success: bool indicating if operation succeeded
        - jobs: array of job objects (format depends on response_format)
        - total: total count of jobs matching filters (before limit applied)
        - filtered: boolean indicating if any filters were applied
        - error: error message if failed

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    import json
    from cluster_registry import get_registry

    # Validate and normalize cluster name
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")
    cluster = cluster.strip()

    # Validate and normalize response_format
    response_format = response_format.strip().lower()
    if response_format not in ["concise", "detailed"]:
        raise ToolError(
            f"Invalid response_format: '{response_format}'. "
            'Must be "concise" or "detailed"'
        )

    # Validate state if provided
    valid_states = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    if state is not None:
        state = state.strip().upper()
        if state and state not in valid_states:
            raise ToolError(
                f"Invalid state: '{state}'. "
                f"Must be one of: {', '.join(valid_states)}"
            )
        # Treat empty string as None
        if not state:
            state = None

    # Normalize user filter
    if user is not None:
        user = user.strip()
        # Treat empty string as None
        if not user:
            user = None

    # Validate limit
    if limit < 1:
        raise ToolError(f"Limit must be >= 1, got {limit}")

    try:
        # Get backend adapter from cluster registry
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # List jobs from backend with filters
        job_details_list = await adapter.list_jobs(
            user=user,
            state=state,
            limit=limit,
        )

        # Determine if filters were applied
        filtered = user is not None or state is not None

        # Format jobs based on response_format
        jobs = []
        for job_details in job_details_list:
            if response_format == "concise":
                jobs.append(job_details.to_concise_dict())
            else:  # detailed
                jobs.append(job_details.to_detailed_dict())

        # Build response
        result = {
            "success": True,
            "jobs": jobs,
            "total": len(jobs),
            "filtered": filtered,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        # Return error response
        result = {
            "success": False,
            "error": str(e),
        }
        return json.dumps(result, indent=2)