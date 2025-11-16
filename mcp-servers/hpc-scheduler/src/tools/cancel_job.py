"""Cancel a running or pending job"""

import json
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp
from cluster_registry import get_registry


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def cancel_job(
    cluster: Annotated[str, Field(description="Cluster name")],
    job_id: Annotated[str, Field(description="Job ID to cancel")],
    signal: Annotated[str, Field(description="Signal to send (default: TERM, options: TERM, KILL, INT)")] = "TERM",
) -> str:
    """Cancel a running or pending job

    Args:
        cluster: Cluster name
        job_id: Job ID to cancel
        signal: Signal to send (default: TERM, options: TERM, KILL, INT)
    Returns:
        JSON object with success status, job_id, state, message, and optional error

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    # Validate inputs
    if not cluster.strip():
        raise ToolError("Cluster name cannot be empty")

    if not job_id.strip():
        raise ToolError("Job ID cannot be empty")

    # Validate signal
    valid_signals = ["TERM", "KILL", "INT"]
    if signal not in valid_signals:
        raise ToolError(f"Invalid signal '{signal}'. Valid options: {', '.join(valid_signals)}")

    try:
        # Get backend adapter for the cluster
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # Cancel the job
        result = await adapter.cancel_job(job_id, signal)

        # Return JSON result
        return json.dumps(result, indent=2)

    except Exception as e:
        # Return error in expected format
        error_result = {
            "success": False,
            "job_id": job_id,
            "state": "UNKNOWN",
            "message": "Failed to cancel job",
            "error": str(e)
        }
        return json.dumps(error_result, indent=2)