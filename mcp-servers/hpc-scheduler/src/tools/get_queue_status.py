"""Get queue statistics and utilization overview"""

import json
from typing import Annotated, Optional
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
async def get_queue_status(
    cluster: Annotated[str, Field(description="Cluster name")],
    response_format: Annotated[
        Optional[str],
        Field(description='Response format: "concise" (default) or "detailed"'),
    ] = "concise",
) -> str:
    """Get queue statistics and utilization overview

    Args:
        cluster: Cluster name
        response_format: Response format: "concise" (default) or "detailed"

    Returns:
        JSON string with queue statistics

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    # Validate and normalize cluster parameter
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")

    cluster = cluster.strip()

    # Validate response_format parameter
    if response_format not in ["concise", "detailed"]:
        raise ToolError(
            f"Invalid response_format '{response_format}'. Must be 'concise' or 'detailed'"
        )

    try:
        # Get cluster adapter
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # Get queue status from adapter
        result = await adapter.get_queue_status(response_format)

        # Return as formatted JSON string
        return json.dumps(result, indent=2)

    except Exception as e:
        raise ToolError(f"Failed to get queue status for cluster '{cluster}': {str(e)}")