"""Tests for get_job tool."""

import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.get_job import get_job

# Access the underlying function for testing (FastMCP decorator pattern)
get_job_fn = get_job.fn


@pytest.mark.asyncio
async def test_get_job_concise_default():
    """Test get_job with default concise format."""
    result = await get_job_fn(cluster="slurm-local", job_id="12345")

    # Parse JSON response
    result_data = json.loads(result)

    # Verify success
    assert result_data["success"] is True

    # Verify concise fields are present
    job = result_data["job"]
    assert job["job_id"] == "12345"
    assert "name" in job
    assert "state" in job
    assert job["state"] in ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    assert "submitted" in job
    assert "runtime" in job
    assert "exit_code" in job

    # Verify detailed fields are NOT present in concise mode
    assert "user" not in job
    assert "partition" not in job
    assert "resources" not in job
    assert "allocated_nodes" not in job


@pytest.mark.asyncio
async def test_get_job_concise_explicit():
    """Test get_job with explicit concise format."""
    result = await get_job_fn(
        cluster="slurm-local", job_id="12345", response_format="concise"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True

    job = result_data["job"]
    assert job["job_id"] == "12345"
    assert "state" in job
    assert "exit_code" in job


@pytest.mark.asyncio
async def test_get_job_detailed():
    """Test get_job with detailed format."""
    result = await get_job_fn(
        cluster="slurm-local", job_id="12345", response_format="detailed"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Verify all concise fields are present
    job = result_data["job"]
    assert job["job_id"] == "12345"
    assert "name" in job
    assert "state" in job
    assert "submitted" in job
    assert "runtime" in job
    assert "exit_code" in job

    # Verify detailed fields are present
    assert "user" in job
    assert "partition" in job
    assert "started" in job
    assert "time_limit" in job
    assert "resources" in job
    assert "allocated_nodes" in job
    assert "working_directory" in job
    assert "stdout_path" in job
    assert "stderr_path" in job

    # Verify resources structure
    resources = job["resources"]
    assert "nodes" in resources
    assert "tasks" in resources
    assert "cpus_per_task" in resources
    assert "memory" in resources


@pytest.mark.asyncio
async def test_get_job_missing_cluster():
    """Test get_job fails when cluster is missing."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_job_fn(cluster="", job_id="12345")


@pytest.mark.asyncio
async def test_get_job_missing_job_id():
    """Test get_job fails when job_id is missing."""
    with pytest.raises(ToolError, match="Job ID cannot be empty"):
        await get_job_fn(cluster="slurm-local", job_id="")


@pytest.mark.asyncio
async def test_get_job_invalid_response_format():
    """Test get_job fails with invalid response_format."""
    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_job_fn(
            cluster="slurm-local", job_id="12345", response_format="invalid"
        )


@pytest.mark.asyncio
async def test_get_job_response_format_case_insensitive():
    """Test get_job handles response_format case-insensitively."""
    # Test uppercase
    result = await get_job_fn(
        cluster="slurm-local", job_id="12345", response_format="CONCISE"
    )
    result_data = json.loads(result)
    assert result_data["success"] is True

    # Test mixed case
    result = await get_job_fn(
        cluster="slurm-local", job_id="12345", response_format="Detailed"
    )
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "user" in result_data["job"]  # Verify it's detailed format


@pytest.mark.asyncio
async def test_get_job_whitespace_handling():
    """Test get_job handles whitespace in parameters correctly."""
    result = await get_job_fn(
        cluster="  slurm-local  ",
        job_id="  12345  ",
        response_format="  concise  ",
    )

    result_data = json.loads(result)
    assert result_data["success"] is True


@pytest.mark.asyncio
async def test_get_job_job_id_in_paths():
    """Test get_job includes job_id in output paths (detailed format)."""
    result = await get_job_fn(
        cluster="slurm-local", job_id="98765", response_format="detailed"
    )

    result_data = json.loads(result)
    job = result_data["job"]

    # Verify job_id is in the paths
    assert "98765" in job["stdout_path"]
    assert "98765" in job["stderr_path"]


@pytest.mark.asyncio
async def test_get_job_valid_job_states():
    """Test get_job returns valid job states."""
    result = await get_job_fn(cluster="slurm-local", job_id="12345")

    result_data = json.loads(result)
    job = result_data["job"]

    # Verify state is one of the valid states from spec
    valid_states = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    assert job["state"] in valid_states


@pytest.mark.asyncio
async def test_get_job_iso8601_timestamps():
    """Test get_job returns ISO8601 formatted timestamps."""
    result = await get_job_fn(
        cluster="slurm-local", job_id="12345", response_format="detailed"
    )

    result_data = json.loads(result)
    job = result_data["job"]

    # Verify ISO8601 format (basic check for Z suffix)
    assert job["submitted"].endswith("Z")
    assert job["started"].endswith("Z")


@pytest.mark.asyncio
async def test_get_job_runtime_format():
    """Test get_job returns runtime in HH:MM:SS format."""
    result = await get_job_fn(cluster="slurm-local", job_id="12345")

    result_data = json.loads(result)
    job = result_data["job"]

    # Verify runtime format (HH:MM:SS)
    runtime_parts = job["runtime"].split(":")
    assert len(runtime_parts) == 3
    assert all(part.isdigit() for part in runtime_parts)
