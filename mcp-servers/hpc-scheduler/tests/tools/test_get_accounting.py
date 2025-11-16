"""Tests for get_accounting tool"""

import os
import json
import pytest
from fastmcp.exceptions import ToolError
from tools.get_accounting import get_accounting
from cluster_registry import get_registry

# Access the underlying function from the FastMCP decorator
get_accounting_fn = get_accounting.fn


@pytest.fixture(autouse=True)
async def setup_mock_backend():
    """Setup mock backend for all tests"""
    os.environ["USE_MOCK_BACKENDS"] = "true"
    # Clear any existing registry
    registry = get_registry()
    await registry.close_all()
    yield
    # Cleanup
    registry = get_registry()
    await registry.close_all()
    if "USE_MOCK_BACKENDS" in os.environ:
        del os.environ["USE_MOCK_BACKENDS"]


@pytest.mark.asyncio
async def test_get_accounting_concise():
    """Test get_accounting with concise format"""
    result_str = await get_accounting_fn(
        cluster="slurm-local", response_format="concise"
    )

    result = json.loads(result_str)
    assert result["success"] is True
    assert "jobs" in result
    assert "total" in result
    assert isinstance(result["jobs"], list)
    assert result["total"] >= 0

    # Check concise fields if jobs exist
    if result["jobs"]:
        job = result["jobs"][0]
        assert "job_id" in job
        assert "name" in job
        assert "user" in job
        assert "state" in job
        assert "exit_code" in job
        assert "runtime" in job
        assert "cpu_time" in job

        # Detailed fields should NOT be present in concise
        assert "memory_used_max" not in job
        assert "cpu_efficiency" not in job


@pytest.mark.asyncio
async def test_get_accounting_detailed():
    """Test get_accounting with detailed format"""
    result_str = await get_accounting_fn(
        cluster="slurm-local", response_format="detailed"
    )

    result = json.loads(result_str)
    assert result["success"] is True

    # Check detailed fields if jobs exist
    if result["jobs"]:
        job = result["jobs"][0]
        # Concise fields
        assert "job_id" in job
        assert "name" in job
        assert "user" in job
        assert "state" in job
        assert "exit_code" in job
        assert "runtime" in job
        assert "cpu_time" in job

        # Detailed fields
        assert "memory_used_max" in job
        assert "memory_requested" in job
        assert "cpu_efficiency" in job
        assert "wait_time" in job
        assert "nodes_used" in job
        assert "submit_time" in job
        assert "start_time" in job
        assert "end_time" in job


@pytest.mark.asyncio
async def test_get_accounting_filter_by_user():
    """Test filtering accounting data by user"""
    result_str = await get_accounting_fn(
        cluster="slurm-local", user="mock-user", response_format="concise"
    )

    result = json.loads(result_str)
    assert result["success"] is True

    # All returned jobs should belong to the specified user
    for job in result["jobs"]:
        assert job["user"] == "mock-user"


@pytest.mark.asyncio
async def test_get_accounting_filter_by_job_id():
    """Test filtering accounting data by specific job ID"""
    # First get a list to find a job ID
    list_result_str = await get_accounting_fn(
        cluster="slurm-local", response_format="concise"
    )
    list_result = json.loads(list_result_str)

    if list_result["jobs"]:
        job_id = list_result["jobs"][0]["job_id"]

        # Now query for that specific job
        result_str = await get_accounting_fn(
            cluster="slurm-local", job_id=job_id, response_format="concise"
        )

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["total"] == 1
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["job_id"] == job_id


@pytest.mark.asyncio
async def test_get_accounting_with_time_range():
    """Test get_accounting with time range filters"""
    result_str = await get_accounting_fn(
        cluster="slurm-local",
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-12-31T23:59:59Z",
        response_format="concise",
    )

    result = json.loads(result_str)
    assert result["success"] is True
    assert "jobs" in result


@pytest.mark.asyncio
async def test_get_accounting_with_limit():
    """Test get_accounting with custom limit"""
    result_str = await get_accounting_fn(cluster="slurm-local", limit=2)

    result = json.loads(result_str)
    assert result["success"] is True
    assert len(result["jobs"]) <= 2


@pytest.mark.asyncio
async def test_get_accounting_empty_cluster_name():
    """Test get_accounting with empty cluster name"""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_accounting_fn(cluster="")


@pytest.mark.asyncio
async def test_get_accounting_invalid_format():
    """Test get_accounting with invalid response format"""
    with pytest.raises(
        ToolError, match="Invalid response_format.*Must be 'concise' or 'detailed'"
    ):
        await get_accounting_fn(cluster="slurm-local", response_format="invalid")


@pytest.mark.asyncio
async def test_get_accounting_invalid_start_time():
    """Test get_accounting with invalid start_time format"""
    with pytest.raises(ToolError, match="start_time must be a valid ISO8601 timestamp"):
        await get_accounting_fn(cluster="slurm-local", start_time="invalid")


@pytest.mark.asyncio
async def test_get_accounting_invalid_end_time():
    """Test get_accounting with invalid end_time format"""
    with pytest.raises(ToolError, match="end_time must be a valid ISO8601 timestamp"):
        await get_accounting_fn(cluster="slurm-local", end_time="bad-date")


@pytest.mark.asyncio
async def test_get_accounting_unknown_cluster():
    """Test get_accounting with unknown cluster"""
    with pytest.raises(ToolError, match="Failed to get accounting data"):
        await get_accounting_fn(cluster="nonexistent-cluster")


@pytest.mark.asyncio
async def test_get_accounting_cpu_time_calculation():
    """Test that CPU time is properly calculated and formatted"""
    result_str = await get_accounting_fn(
        cluster="slurm-local", response_format="concise"
    )

    result = json.loads(result_str)

    if result["jobs"]:
        job = result["jobs"][0]
        # CPU time should be in HH:MM:SS format
        assert "cpu_time" in job
        parts = job["cpu_time"].split(":")
        assert len(parts) == 3
        # All parts should be numeric
        for part in parts:
            assert part.isdigit()
