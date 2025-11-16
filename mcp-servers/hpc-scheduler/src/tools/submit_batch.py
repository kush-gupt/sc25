"""Submit multiple jobs as an array or batch"""

import json
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp
from cluster_registry import get_registry


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def submit_batch(
    cluster: Annotated[str, Field(description="Cluster name")],
    script: Annotated[str, Field(description="Base job script (may include array task variable)")],
    array_spec: Annotated[str | None, Field(description="Array specification for Slurm (e.g., 1-10, 1-100:2)")] = None,
    commands: Annotated[list[str] | None, Field(description="List of commands for Flux bulk submission")] = None,
    job_name_prefix: Annotated[str | None, Field(description="Prefix for job names")] = None,
    nodes: Annotated[int | None, Field(description="Nodes per job")] = None,
    tasks_per_node: Annotated[int | None, Field(description="Tasks per node per job")] = None,
    time_limit: Annotated[str | None, Field(description="Time limit per job")] = None,
    max_concurrent: Annotated[int | None, Field(description="Maximum concurrent jobs (Slurm arrays only)")] = None,
    response_format: Annotated[str, Field(description="Response format: concise (default) or detailed")] = "concise",
) -> str:
    """Submit multiple jobs as an array or batch

    Args:
        cluster: Cluster name
        script: Base job script (may include array task variable)
        array_spec: Array specification for Slurm (e.g., 1-10, 1-100:2)
        commands: List of commands for Flux bulk submission
        job_name_prefix: Prefix for job names
        nodes: Nodes per job
        tasks_per_node: Tasks per node per job
        time_limit: Time limit per job
        max_concurrent: Maximum concurrent jobs (Slurm arrays only)
        response_format: Response format: concise (default) or detailed
    Returns:
        JSON string with batch submission results

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    try:
        # Input validation
        if not cluster or not cluster.strip():
            raise ToolError("Cluster name cannot be empty")

        if not script or not script.strip():
            raise ToolError("Script cannot be empty")

        if not array_spec and not commands:
            raise ToolError("Either array_spec (for Slurm) or commands (for Flux) must be provided")

        if array_spec and commands:
            raise ToolError("Cannot specify both array_spec and commands - use one or the other")

        # Validate response_format
        if response_format not in ["concise", "detailed"]:
            raise ToolError("response_format must be 'concise' or 'detailed'")

        # Get cluster adapter
        registry = get_registry()
        adapter = registry.get_adapter(cluster)

        # Submit batch jobs
        result = await adapter.submit_batch(
            script=script,
            array_spec=array_spec,
            commands=commands,
            job_name_prefix=job_name_prefix,
            nodes=nodes,
            tasks_per_node=tasks_per_node,
            time_limit=time_limit,
            max_concurrent=max_concurrent,
        )

        # Format response based on response_format
        if response_format == "concise":
            # Return concise version - just key fields
            concise_result = {
                "success": result["success"],
                "job_ids": result["job_ids"],
                "batch_type": result["batch_type"],
                "submitted": result["submitted"],
                "failed": result["failed"],
            }
            # Only include errors if there are any
            if result["failed"] > 0:
                concise_result["errors"] = result["errors"]

            return json.dumps(concise_result, indent=2)
        else:
            # Return detailed version - all fields
            return json.dumps(result, indent=2)

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to submit batch jobs: {str(e)}")