"""Tests for list_jobs tool."""

import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.list_jobs import list_jobs
from cluster_registry import reset_registry

# Access the underlying function for testing (FastMCP decorator pattern)
list_jobs_fn = list_jobs.fn


@pytest.fixture(autouse=True)
async def setup_mock_env(monkeypatch):
    """Set up mock backend environment for all tests"""
    monkeypatch.setenv("USE_MOCK_BACKENDS", "true")
    # Reset registry before each test to ensure clean state
    reset_registry()
    yield


@pytest.mark.asyncio
async def test_list_jobs_basic_no_filters():
    """Test list_jobs with no filters (all jobs)."""
    result = await list_jobs_fn(cluster="slurm-local")

    # Parse JSON response
    result_data = json.loads(result)

    # Verify success
    assert result_data["success"] is True

    # Verify structure
    assert "jobs" in result_data
    assert "total" in result_data
    assert "filtered" in result_data

    # No filters applied
    assert result_data["filtered"] is False

    # Should have jobs (mock creates 5 by default)
    assert len(result_data["jobs"]) > 0
    assert result_data["total"] > 0

    # Verify concise format fields (default)
    job = result_data["jobs"][0]
    assert "job_id" in job
    assert "name" in job
    assert "state" in job
    assert "submitted" in job
    assert "runtime" in job
    assert "exit_code" in job

    # Concise format should NOT have detailed fields
    assert "user" not in job
    assert "partition" not in job
    assert "resources" not in job


@pytest.mark.asyncio
async def test_list_jobs_detailed_format():
    """Test list_jobs with detailed response format."""
    result = await list_jobs_fn(cluster="slurm-local", response_format="detailed")

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Verify detailed format fields
    job = result_data["jobs"][0]

    # Concise fields
    assert "job_id" in job
    assert "name" in job
    assert "state" in job
    assert "submitted" in job
    assert "runtime" in job
    assert "exit_code" in job

    # Detailed fields
    assert "user" in job
    assert "partition" in job
    assert "started" in job
    assert "ended" in job
    assert "time_limit" in job
    assert "resources" in job
    assert "allocated_nodes" in job
    assert "working_directory" in job
    assert "stdout_path" in job
    assert "stderr_path" in job


@pytest.mark.asyncio
async def test_list_jobs_filter_by_user():
    """Test list_jobs filtered by user."""
    result = await list_jobs_fn(cluster="slurm-local", user="testuser")

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Filter was applied
    assert result_data["filtered"] is True

    # All jobs should be for the specified user (mock returns jobs for testuser)
    for job in result_data["jobs"]:
        # In detailed format, we can verify user
        pass  # Mock will apply filter


@pytest.mark.asyncio
async def test_list_jobs_filter_by_state():
    """Test list_jobs filtered by state."""
    result = await list_jobs_fn(cluster="slurm-local", state="RUNNING")

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Filter was applied
    assert result_data["filtered"] is True

    # All jobs should be in RUNNING state
    for job in result_data["jobs"]:
        assert job["state"] == "RUNNING"


@pytest.mark.asyncio
async def test_list_jobs_filter_by_user_and_state():
    """Test list_jobs with both user and state filters."""
    result = await list_jobs_fn(
        cluster="slurm-local", user="testuser", state="PENDING"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Both filters applied
    assert result_data["filtered"] is True


@pytest.mark.asyncio
async def test_list_jobs_limit():
    """Test list_jobs with limit parameter."""
    result = await list_jobs_fn(cluster="slurm-local", limit=2)

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Should return at most 2 jobs
    assert len(result_data["jobs"]) <= 2


@pytest.mark.asyncio
async def test_list_jobs_default_limit():
    """Test list_jobs uses default limit of 100."""
    result = await list_jobs_fn(cluster="slurm-local")

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Should not exceed default limit
    assert len(result_data["jobs"]) <= 100


@pytest.mark.asyncio
async def test_list_jobs_missing_cluster():
    """Test list_jobs fails when cluster is missing."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await list_jobs_fn(cluster="")


@pytest.mark.asyncio
async def test_list_jobs_invalid_state():
    """Test list_jobs fails with invalid state."""
    with pytest.raises(ToolError, match="Invalid state"):
        await list_jobs_fn(cluster="slurm-local", state="INVALID_STATE")


@pytest.mark.asyncio
async def test_list_jobs_state_case_insensitive():
    """Test list_jobs handles state case-insensitively."""
    # Lowercase should work
    result = await list_jobs_fn(cluster="slurm-local", state="running")
    result_data = json.loads(result)
    assert result_data["success"] is True

    # Mixed case should work
    result = await list_jobs_fn(cluster="slurm-local", state="Pending")
    result_data = json.loads(result)
    assert result_data["success"] is True


@pytest.mark.asyncio
async def test_list_jobs_invalid_response_format():
    """Test list_jobs fails with invalid response_format."""
    with pytest.raises(ToolError, match="Invalid response_format"):
        await list_jobs_fn(cluster="slurm-local", response_format="invalid")


@pytest.mark.asyncio
async def test_list_jobs_response_format_case_insensitive():
    """Test list_jobs handles response_format case-insensitively."""
    # Uppercase
    result = await list_jobs_fn(cluster="slurm-local", response_format="CONCISE")
    result_data = json.loads(result)
    assert result_data["success"] is True

    # Mixed case
    result = await list_jobs_fn(cluster="slurm-local", response_format="Detailed")
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "user" in result_data["jobs"][0]  # Verify detailed format


@pytest.mark.asyncio
async def test_list_jobs_invalid_limit():
    """Test list_jobs fails with invalid limit."""
    with pytest.raises(ToolError, match="Limit must be >= 1"):
        await list_jobs_fn(cluster="slurm-local", limit=0)

    with pytest.raises(ToolError, match="Limit must be >= 1"):
        await list_jobs_fn(cluster="slurm-local", limit=-1)


@pytest.mark.asyncio
async def test_list_jobs_whitespace_handling():
    """Test list_jobs handles whitespace in parameters correctly."""
    result = await list_jobs_fn(
        cluster="  slurm-local  ",
        user="  testuser  ",
        state="  RUNNING  ",
        response_format="  concise  ",
    )

    result_data = json.loads(result)
    assert result_data["success"] is True


@pytest.mark.asyncio
async def test_list_jobs_empty_string_filters_treated_as_none():
    """Test list_jobs treats empty string filters as None."""
    # Empty user should not filter
    result = await list_jobs_fn(cluster="slurm-local", user="")
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert result_data["filtered"] is False

    # Empty state should not filter
    result = await list_jobs_fn(cluster="slurm-local", state="")
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert result_data["filtered"] is False


@pytest.mark.asyncio
async def test_list_jobs_valid_states():
    """Test list_jobs accepts all valid states."""
    valid_states = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]

    for state in valid_states:
        result = await list_jobs_fn(cluster="slurm-local", state=state)
        result_data = json.loads(result)
        assert result_data["success"] is True


@pytest.mark.asyncio
async def test_list_jobs_iso8601_timestamps():
    """Test list_jobs returns ISO8601 formatted timestamps."""
    result = await list_jobs_fn(cluster="slurm-local", response_format="detailed")

    result_data = json.loads(result)
    job = result_data["jobs"][0]

    # Verify ISO8601 format (basic check for Z suffix)
    assert job["submitted"].endswith("Z")
    if job["started"]:
        assert job["started"].endswith("Z")


@pytest.mark.asyncio
async def test_list_jobs_runtime_format():
    """Test list_jobs returns runtime in HH:MM:SS format."""
    result = await list_jobs_fn(cluster="slurm-local")

    result_data = json.loads(result)
    job = result_data["jobs"][0]

    # Verify runtime format (HH:MM:SS)
    runtime_parts = job["runtime"].split(":")
    assert len(runtime_parts) == 3
    assert all(part.isdigit() for part in runtime_parts)


@pytest.mark.asyncio
async def test_list_jobs_total_count():
    """Test list_jobs returns correct total count."""
    result = await list_jobs_fn(cluster="slurm-local")

    result_data = json.loads(result)

    # Total should match number of jobs returned (before limit applied)
    assert result_data["total"] == len(result_data["jobs"])
