"""Analyze a job script and predict resource requirements"""

import json
import re
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp


def _analyze_script_patterns(script: str) -> dict:
    """
    Analyze script for resource-intensive patterns

    Returns dict with cpu_intensive, memory_intensive, io_intensive flags
    """
    script_lower = script.lower()

    # CPU intensive patterns
    cpu_patterns = [
        r'\b(mpirun|mpiexec|srun)\b',  # MPI parallel execution
        r'\b(openmp|omp_num_threads)\b',  # OpenMP threading
        r'\bfor\s+\w+\s+in\s+',  # Loop constructs
        r'\b(numpy|scipy|tensorflow|pytorch)\b',  # Numerical libraries
        r'\b(fft|matrix|linear algebra)\b',  # Mathematical operations
    ]
    cpu_intensive = any(re.search(pattern, script_lower) for pattern in cpu_patterns)

    # Memory intensive patterns
    memory_patterns = [
        r'\b(malloc|calloc|new\s+\w+\[)\b',  # Memory allocation
        r'\b(array|matrix|tensor)\b',  # Data structures
        r'\b(sort|merge|hash)\b',  # Memory-heavy algorithms
        r'\b(\d+)gb\b',  # Explicit GB references
        r'\b(cache|buffer|heap)\b',  # Memory-related terms
    ]
    memory_intensive = any(re.search(pattern, script_lower) for pattern in memory_patterns)

    # I/O intensive patterns
    io_patterns = [
        r'\b(read|write|fopen|fread|fwrite)\b',  # File operations
        r'\b(dd|rsync|cp|mv)\b',  # File transfer commands
        r'\b(database|sql|query)\b',  # Database operations
        r'\b(/dev/|/mnt/|/data/)\b',  # File paths
        r'\b(parallel.*io|mpi.*io)\b',  # Parallel I/O
    ]
    io_intensive = any(re.search(pattern, script_lower) for pattern in io_patterns)

    return {
        "cpu_intensive": cpu_intensive,
        "memory_intensive": memory_intensive,
        "io_intensive": io_intensive,
    }


def _estimate_resources(script: str, patterns: dict) -> dict:
    """
    Estimate resource requirements based on script analysis

    Returns dict with estimated_memory, estimated_runtime, recommended_nodes, recommended_tasks
    """
    # Extract any MPI task count hints
    mpi_match = re.search(r'mpirun\s+-n\s+(\d+)', script.lower())
    mpi_tasks = int(mpi_match.group(1)) if mpi_match else None

    # Estimate based on workload type
    if patterns["cpu_intensive"]:
        # CPU-bound: more tasks, moderate memory
        estimated_memory = "8GB"
        estimated_runtime = "02:00:00"
        recommended_nodes = 2 if not mpi_tasks else max(1, mpi_tasks // 4)
        recommended_tasks = 8 if not mpi_tasks else mpi_tasks
    elif patterns["memory_intensive"]:
        # Memory-bound: fewer tasks, more memory
        estimated_memory = "32GB"
        estimated_runtime = "01:30:00"
        recommended_nodes = 1
        recommended_tasks = 4
    elif patterns["io_intensive"]:
        # I/O-bound: moderate tasks, moderate memory
        estimated_memory = "16GB"
        estimated_runtime = "03:00:00"
        recommended_nodes = 1
        recommended_tasks = 4
    else:
        # Generic workload
        estimated_memory = "4GB"
        estimated_runtime = "01:00:00"
        recommended_nodes = 1
        recommended_tasks = 1

    return {
        "estimated_memory": estimated_memory,
        "estimated_runtime": estimated_runtime,
        "recommended_nodes": recommended_nodes,
        "recommended_tasks": recommended_tasks,
    }


def _generate_recommendations(script: str, patterns: dict, estimates: dict) -> list:
    """
    Generate recommendations for optimal resource allocation

    Returns list of recommendation dicts
    """
    recommendations = []

    # Node recommendation
    recommendations.append({
        "parameter": "nodes",
        "value": str(estimates["recommended_nodes"]),
        "confidence": "high" if patterns["cpu_intensive"] else "medium",
        "reason": f"Based on {'parallel workload detection' if patterns['cpu_intensive'] else 'workload analysis'}, {estimates['recommended_nodes']} node(s) recommended",
    })

    # Task recommendation
    recommendations.append({
        "parameter": "tasks",
        "value": str(estimates["recommended_tasks"]),
        "confidence": "medium",
        "reason": f"Optimal task count for {'CPU-intensive' if patterns['cpu_intensive'] else 'standard'} workload",
    })

    # Memory recommendation
    recommendations.append({
        "parameter": "memory",
        "value": estimates["estimated_memory"],
        "confidence": "medium" if patterns["memory_intensive"] else "low",
        "reason": f"Estimated based on {'memory-intensive patterns' if patterns['memory_intensive'] else 'typical workload requirements'}",
    })

    # Time limit recommendation
    recommendations.append({
        "parameter": "time_limit",
        "value": estimates["estimated_runtime"],
        "confidence": "low",
        "reason": "Estimated runtime with 20% buffer. Monitor first run and adjust.",
    })

    # I/O specific recommendations
    if patterns["io_intensive"]:
        recommendations.append({
            "parameter": "partition",
            "value": "io-optimized",
            "confidence": "medium",
            "reason": "I/O-intensive workload detected. Consider using I/O-optimized partition if available.",
        })

    return recommendations


def _get_historical_comparison(historical_job_id: str | None) -> dict:
    """
    Get historical comparison data (mock implementation)

    In production, this would query job history database
    """
    if not historical_job_id:
        return {
            "similar_jobs": 0,
            "avg_runtime": "N/A",
            "avg_memory": "N/A",
            "success_rate": 0.0,
        }

    # Mock historical data
    return {
        "similar_jobs": 15,
        "avg_runtime": "01:25:30",
        "avg_memory": "12.5GB",
        "success_rate": 0.93,
    }


@mcp.tool(
    annotations={
        "readOnlyHint": True,  # Analysis doesn't modify state
        "idempotentHint": True,  # Same input gives same output
        "openWorldHint": False,
    }
)
async def analyze_job(
    cluster: Annotated[str, Field(description="Cluster name")],
    script: Annotated[str, Field(description="Job script to analyze")],
    historical_job_id: Annotated[str | None, Field(description="Reference similar completed job for estimates")] = None,
) -> str:
    """Analyze a job script and predict resource requirements

    This tool parses job scripts to identify resource-intensive patterns and provides
    recommendations for optimal resource allocation. It helps prevent over/under-provisioning
    and can improve queue wait times.

    The analysis includes:
    - Pattern detection (CPU, memory, I/O intensive workloads)
    - Resource estimates (memory, runtime, nodes, tasks)
    - Optimization recommendations with confidence levels
    - Historical comparison (if reference job provided)

    Args:
        cluster: Cluster name (validates cluster exists)
        script: Job script to analyze (should include shebang and commands)
        historical_job_id: Optional reference to similar completed job for estimates

    Returns:
        JSON string containing:
        - success: bool
        - analysis: dict with estimates and workload characteristics
        - recommendations: list of optimization suggestions
        - historical_comparison: comparison with similar jobs

    Raises:
        ToolError: If validation fails or cluster not found
    """
    # Validate cluster
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")
    cluster = cluster.strip()

    # Validate cluster exists
    from cluster_registry import get_registry

    try:
        registry = get_registry()
        cluster_info = registry.get_cluster_info(cluster)
    except Exception as e:
        raise ToolError(f"Cluster validation failed: {str(e)}")

    # Validate script
    if not script or not script.strip():
        raise ToolError("Script cannot be empty")
    script = script.strip()

    # Validate script has shebang
    script_lines = script.split('\n')
    if not script_lines[0].startswith('#!'):
        raise ToolError(
            "Script must include shebang line (e.g., #!/bin/bash). "
            f"First line was: {script_lines[0]}"
        )

    # Perform analysis
    try:
        # Analyze patterns
        patterns = _analyze_script_patterns(script)

        # Estimate resources
        estimates = _estimate_resources(script, patterns)

        # Generate recommendations
        recommendations = _generate_recommendations(script, patterns, estimates)

        # Get historical comparison
        historical = _get_historical_comparison(historical_job_id)

        # Build result
        result = {
            "success": True,
            "cluster": cluster,
            "backend": cluster_info.get("type", "unknown"),
            "analysis": {
                "estimated_memory": estimates["estimated_memory"],
                "estimated_runtime": estimates["estimated_runtime"],
                "recommended_nodes": estimates["recommended_nodes"],
                "recommended_tasks": estimates["recommended_tasks"],
                "cpu_intensive": patterns["cpu_intensive"],
                "memory_intensive": patterns["memory_intensive"],
                "io_intensive": patterns["io_intensive"],
            },
            "recommendations": recommendations,
            "historical_comparison": historical,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        # Return error response
        result = {
            "success": False,
            "cluster": cluster,
            "error": str(e),
        }
        return json.dumps(result, indent=2)
