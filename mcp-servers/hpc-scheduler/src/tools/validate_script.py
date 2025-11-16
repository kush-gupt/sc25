"""Validate a job script before submission (pre-flight checks)"""

import json
import re
from typing import Annotated, Optional
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp
from cluster_registry import get_registry


@mcp.tool(
    annotations={
        "readOnlyHint": True,  # Validation is read-only, doesn't submit
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def validate_script(
    cluster: Annotated[str, Field(description="Cluster name")],
    script: Annotated[str, Field(description="Job script to validate")],
    nodes: Annotated[Optional[int], Field(description="Intended node count")] = None,
    time_limit: Annotated[Optional[str], Field(description="Intended time limit")] = None,
    partition: Annotated[Optional[str], Field(description="Target partition (Slurm)")] = None,
) -> str:
    """Validate a job script before submission (pre-flight checks)

    Args:
        cluster: Cluster name
        script: Job script to validate
        nodes: Intended node count
        time_limit: Intended time limit
        partition: Target partition (Slurm)
    Returns:
        JSON string containing validation results with issues and recommendations

    Raises:
        ToolError: If validation operation cannot be completed
    """
    # Validate input parameters
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")

    if not script or not script.strip():
        raise ToolError("Script cannot be empty")

    cluster = cluster.strip()
    script = script.strip()

    # Initialize validation result
    issues = []
    recommendations = []
    valid = True  # Start optimistic, set to False if errors found

    # Get cluster resources to validate against limits
    try:
        registry = get_registry()
        adapter = registry.get_adapter(cluster)
        cluster_info = registry.get_cluster_info(cluster)
        backend_type = cluster_info.get("type", "unknown")

        # Get detailed resource information for validation
        resources_result = await adapter.get_resources("detailed")

    except Exception as e:
        raise ToolError(f"Failed to get cluster information for '{cluster}': {str(e)}")

    # Syntax checks
    script_lines = script.split('\n')

    # Check for shebang
    if not script_lines[0].startswith('#!'):
        issues.append({
            "severity": "error",
            "category": "syntax",
            "message": "Script missing shebang line (e.g., #!/bin/bash)",
            "line": 1
        })
        valid = False

    # Resource validation - nodes
    if nodes is not None:
        if nodes < 1:
            issues.append({
                "severity": "error",
                "category": "resources",
                "message": f"Node count must be >= 1, got {nodes}"
            })
            valid = False
        else:
            # Check against cluster limits
            total_nodes = resources_result.get("nodes", {}).get("total", 0)
            idle_nodes = resources_result.get("nodes", {}).get("idle", 0)

            if total_nodes > 0 and nodes > total_nodes:
                issues.append({
                    "severity": "error",
                    "category": "resources",
                    "message": f"Requested {nodes} nodes, but cluster only has {total_nodes} total nodes"
                })
                recommendations.append({
                    "field": "nodes",
                    "current": str(nodes),
                    "suggested": str(total_nodes),
                    "reason": "Cluster maximum"
                })
                valid = False
            elif idle_nodes > 0 and nodes > idle_nodes:
                issues.append({
                    "severity": "warning",
                    "category": "resources",
                    "message": f"Requested {nodes} nodes, but only {idle_nodes} nodes currently idle (cluster has {total_nodes} total)"
                })

    # Resource validation - time_limit
    if time_limit is not None:
        time_limit = time_limit.strip()
        if not time_limit:
            issues.append({
                "severity": "error",
                "category": "syntax",
                "message": "Time limit parameter cannot be empty string"
            })
            valid = False
        else:
            # Validate time format
            valid_formats = [
                r'^\d+[hms]$',  # 1h, 30m, 60s
                r'^\d+:\d+$',  # 1:30 (minutes:seconds)
                r'^\d+:\d+:\d+$',  # 1:30:00 (hours:minutes:seconds)
            ]
            if not any(re.match(pattern, time_limit, re.IGNORECASE) for pattern in valid_formats):
                issues.append({
                    "severity": "error",
                    "category": "syntax",
                    "message": f"Invalid time limit format: {time_limit}. Expected formats: 1h, 30m, 60s, 1:30, or 1:30:00"
                })
                valid = False

    # Partition validation (Slurm-specific)
    if partition is not None and backend_type == "slurm":
        partition = partition.strip()
        partitions_info = resources_result.get("partitions", [])

        if partitions_info:
            partition_names = [p.get("name") for p in partitions_info]
            partition_states = {p.get("name"): p.get("state") for p in partitions_info}

            if partition not in partition_names:
                issues.append({
                    "severity": "error",
                    "category": "resources",
                    "message": f"Partition '{partition}' does not exist. Available partitions: {', '.join(partition_names)}"
                })
                valid = False
            elif partition_states.get(partition) != "UP":
                issues.append({
                    "severity": "warning",
                    "category": "resources",
                    "message": f"Partition '{partition}' is not UP (current state: {partition_states.get(partition)})"
                })

    # Check for common issues in script content

    # Warn if script appears to have no actual commands (only comments/whitespace)
    non_comment_lines = [line for line in script_lines if line.strip() and not line.strip().startswith('#')]
    if len(non_comment_lines) == 0:
        issues.append({
            "severity": "warning",
            "category": "syntax",
            "message": "Script contains no executable commands (only comments or whitespace)"
        })

    # Check for potential module load issues
    if 'module load' in script.lower():
        issues.append({
            "severity": "info",
            "category": "compatibility",
            "message": "Script uses 'module load' - ensure modules are available on target cluster"
        })

    # Build result
    result = {
        "success": True,
        "valid": valid,
        "issues": issues,
        "recommendations": recommendations
    }

    return json.dumps(result, indent=2)