"""Tests for get_queue_status tool."""

import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.get_queue_status import get_queue_status

# Access the underlying function for testing (FastMCP decorator pattern)
get_queue_status_fn = get_queue_status.fn


@pytest.mark.asyncio
async def test_get_queue_status_concise_format():
    """Test get_queue_status with concise format (default)."""
    result = await get_queue_status_fn(
        cluster="slurm-local",
        response_format="concise"
    )

    # Parse JSON response
    result_data = json.loads(result)

    # Verify concise format fields
    assert result_data["success"] is True
    assert result_data["cluster"] == "slurm-local"
    assert "total_jobs" in result_data
    assert "running" in result_data
    assert "pending" in result_data
    assert "completed" in result_data

    # Ensure concise format does not include detailed fields
    assert "failed" not in result_data
    assert "cancelled" not in result_data
    assert "utilization" not in result_data
    assert "recent_jobs" not in result_data


@pytest.mark.asyncio
async def test_get_queue_status_default_format():
    """Test get_queue_status defaults to concise format."""
    result = await get_queue_status_fn(cluster="slurm-local")

    result_data = json.loads(result)

    # Should behave like concise format
    assert result_data["success"] is True
    assert "total_jobs" in result_data
    assert "failed" not in result_data
    assert "utilization" not in result_data


@pytest.mark.asyncio
async def test_get_queue_status_detailed_format():
    """Test get_queue_status with detailed format."""
    result = await get_queue_status_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)

    # Verify all concise fields are present
    assert result_data["success"] is True
    assert result_data["cluster"] == "slurm-local"
    assert "total_jobs" in result_data
    assert "running" in result_data
    assert "pending" in result_data
    assert "completed" in result_data

    # Verify detailed-specific fields
    assert "failed" in result_data
    assert "cancelled" in result_data
    assert "utilization" in result_data
    assert "recent_jobs" in result_data

    # Verify utilization structure
    utilization = result_data["utilization"]
    assert "nodes_allocated" in utilization
    assert "nodes_total" in utilization
    assert "cores_allocated" in utilization
    assert "cores_total" in utilization

    # Verify recent_jobs structure
    recent_jobs = result_data["recent_jobs"]
    assert isinstance(recent_jobs, list)
    # Check that jobs are limited to 20
    assert len(recent_jobs) <= 20

    # If there are recent jobs, verify structure
    if recent_jobs:
        job = recent_jobs[0]
        assert "job_id" in job
        assert "name" in job
        assert "state" in job
        assert "runtime" in job


@pytest.mark.asyncio
async def test_get_queue_status_recent_jobs_limit():
    """Test that recent_jobs is limited to 20 entries."""
    result = await get_queue_status_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)
    recent_jobs = result_data["recent_jobs"]

    # Should never exceed 20 jobs
    assert len(recent_jobs) <= 20


@pytest.mark.asyncio
async def test_get_queue_status_missing_cluster():
    """Test get_queue_status fails when cluster is empty."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_queue_status_fn(cluster="")


@pytest.mark.asyncio
async def test_get_queue_status_whitespace_cluster():
    """Test get_queue_status fails when cluster is whitespace."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_queue_status_fn(cluster="   ")


@pytest.mark.asyncio
async def test_get_queue_status_invalid_format():
    """Test get_queue_status fails with invalid response_format."""
    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_queue_status_fn(
            cluster="slurm-local",
            response_format="invalid"
        )


@pytest.mark.asyncio
async def test_get_queue_status_numeric_values():
    """Test that numeric fields are integers."""
    result = await get_queue_status_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)

    # Verify numeric types
    assert isinstance(result_data["total_jobs"], int)
    assert isinstance(result_data["running"], int)
    assert isinstance(result_data["pending"], int)
    assert isinstance(result_data["completed"], int)
    assert isinstance(result_data["failed"], int)
    assert isinstance(result_data["cancelled"], int)

    utilization = result_data["utilization"]
    assert isinstance(utilization["nodes_allocated"], int)
    assert isinstance(utilization["nodes_total"], int)
    assert isinstance(utilization["cores_allocated"], int)
    assert isinstance(utilization["cores_total"], int)


@pytest.mark.asyncio
async def test_get_queue_status_non_negative_counts():
    """Test that job counts are non-negative."""
    result = await get_queue_status_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)

    # All counts should be >= 0
    assert result_data["total_jobs"] >= 0
    assert result_data["running"] >= 0
    assert result_data["pending"] >= 0
    assert result_data["completed"] >= 0
    assert result_data["failed"] >= 0
    assert result_data["cancelled"] >= 0


@pytest.mark.asyncio
async def test_get_queue_status_flux_cluster():
    """Test get_queue_status works with flux-local cluster."""
    result = await get_queue_status_fn(
        cluster="flux-local",
        response_format="concise"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert result_data["cluster"] == "flux-local"


@pytest.mark.asyncio
async def test_get_queue_status_whitespace_trimming():
    """Test get_queue_status handles whitespace in cluster parameter."""
    result = await get_queue_status_fn(
        cluster="  slurm-local  ",
        response_format="concise"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True


@pytest.mark.asyncio
async def test_get_queue_status_case_sensitive_format():
    """Test that response_format validation is case-sensitive."""
    # These should fail (case-sensitive validation)
    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_queue_status_fn(
            cluster="slurm-local",
            response_format="Concise"
        )

    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_queue_status_fn(
            cluster="slurm-local",
            response_format="DETAILED"
        )
