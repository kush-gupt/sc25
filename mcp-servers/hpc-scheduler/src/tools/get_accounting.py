"""Get historical job accounting and performance data"""

import json
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp
from cluster_registry import get_registry


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def get_accounting(
    cluster: Annotated[str, Field(description="Cluster name")],
    job_id: Annotated[str | None, Field(description="Specific job ID to query")] = None,
    user: Annotated[str | None, Field(description="Filter by username")] = None,
    start_time: Annotated[
        str | None, Field(description="Start of time range (ISO8601)")
    ] = None,
    end_time: Annotated[str | None, Field(description="End of time range (ISO8601)")] = None,
    limit: Annotated[int, Field(description="Maximum records to return", ge=1, le=1000)] = 100,
    response_format: Annotated[
        str, Field(description="Response format: concise (default) or detailed")
    ] = "concise",
) -> str:
    """Get historical job accounting and performance data

    Args:
        cluster: Cluster name
        job_id: Specific job ID to query
        user: Filter by username
        start_time: Start of time range (ISO8601)
        end_time: End of time range (ISO8601)
        limit: Maximum records to return (1-1000, default 100)
        response_format: Response format: concise (default) or detailed

    Returns:
        JSON string with accounting data including job history and performance metrics

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    # Validate inputs
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")

    if response_format not in ["concise", "detailed"]:
        raise ToolError(
            f"Invalid response_format '{response_format}'. Must be 'concise' or 'detailed'"
        )

    # Validate ISO8601 timestamps if provided (basic check)
    for time_param, time_value in [("start_time", start_time), ("end_time", end_time)]:
        if time_value:
            if not isinstance(time_value, str) or len(time_value) < 10:
                raise ToolError(
                    f"{time_param} must be a valid ISO8601 timestamp (e.g., '2025-01-01T00:00:00Z')"
                )

    try:
        # Get cluster adapter
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # Get accounting data from backend
        result = await adapter.get_accounting(
            job_id=job_id,
            user=user,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            response_format=response_format,
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        raise ToolError(f"Failed to get accounting data: {str(e)}")