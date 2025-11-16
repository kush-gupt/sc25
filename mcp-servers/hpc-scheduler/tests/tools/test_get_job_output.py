"""Tests for get_job_output tool."""

import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.get_job_output import get_job_output

# Access the underlying function for testing (FastMCP decorator pattern)
get_job_output_fn = get_job_output.fn


@pytest.mark.asyncio
async def test_get_job_output_stdout_default():
    """Test get_job_output with default stdout output."""
    result = await get_job_output_fn(
        cluster="slurm-local",
        job_id="12345"
    )

    # Parse JSON response
    result_data = json.loads(result)

    assert result_data["success"] is True
    assert result_data["job_id"] == "12345"
    assert "stdout" in result_data
    assert result_data["truncated"] is False


@pytest.mark.asyncio
async def test_get_job_output_stdout_explicit():
    """Test get_job_output with explicit stdout output_type."""
    result = await get_job_output_fn(
        cluster="slurm-local",
        job_id="12345",
        output_type="stdout"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "stdout" in result_data
    assert "stderr" not in result_data


@pytest.mark.asyncio
async def test_get_job_output_stderr():
    """Test get_job_output with stderr output_type."""
    result = await get_job_output_fn(
        cluster="slurm-local",
        job_id="12345",
        output_type="stderr"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "stderr" in result_data
    assert "stdout" not in result_data


@pytest.mark.asyncio
async def test_get_job_output_both():
    """Test get_job_output with both stdout and stderr."""
    result = await get_job_output_fn(
        cluster="slurm-local",
        job_id="12345",
        output_type="both"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "stdout" in result_data
    assert "stderr" in result_data


@pytest.mark.asyncio
async def test_get_job_output_tail_lines():
    """Test get_job_output with tail_lines parameter."""
    result = await get_job_output_fn(
        cluster="slurm-local",
        job_id="12345",
        output_type="stdout",
        tail_lines=2
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "stdout" in result_data
    # Mock adapter returns 4 lines, so tail_lines=2 should truncate
    assert result_data["truncated"] is True


@pytest.mark.asyncio
async def test_get_job_output_missing_cluster():
    """Test get_job_output fails when cluster is missing."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_job_output_fn(
            cluster="",
            job_id="12345"
        )


@pytest.mark.asyncio
async def test_get_job_output_missing_job_id():
    """Test get_job_output fails when job_id is missing."""
    with pytest.raises(ToolError, match="Job ID cannot be empty"):
        await get_job_output_fn(
            cluster="slurm-local",
            job_id=""
        )


@pytest.mark.asyncio
async def test_get_job_output_invalid_output_type():
    """Test get_job_output fails with invalid output_type."""
    with pytest.raises(ToolError, match="Invalid output_type"):
        await get_job_output_fn(
            cluster="slurm-local",
            job_id="12345",
            output_type="invalid"
        )


@pytest.mark.asyncio
async def test_get_job_output_invalid_tail_lines():
    """Test get_job_output fails with invalid tail_lines."""
    with pytest.raises(ToolError, match="tail_lines must be >= 1"):
        await get_job_output_fn(
            cluster="slurm-local",
            job_id="12345",
            tail_lines=0
        )


@pytest.mark.asyncio
async def test_get_job_output_whitespace_trimming():
    """Test get_job_output handles whitespace in parameters correctly."""
    result = await get_job_output_fn(
        cluster="  slurm-local  ",
        job_id="  12345  ",
        output_type="  stdout  "
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert result_data["job_id"] == "12345"


@pytest.mark.asyncio
async def test_get_job_output_case_insensitive_output_type():
    """Test get_job_output handles output_type case-insensitively."""
    # Test various case combinations
    for output_type in ["STDOUT", "Stderr", "BOTH", "StdOut"]:
        result = await get_job_output_fn(
            cluster="slurm-local",
            job_id="12345",
            output_type=output_type
        )
        result_data = json.loads(result)
        assert result_data["success"] is True
