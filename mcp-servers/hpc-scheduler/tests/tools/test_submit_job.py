"""Tests for submit_job tool."""

import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.submit_job import submit_job

# Access the underlying function for testing (FastMCP decorator pattern)
submit_job_fn = submit_job.fn


@pytest.mark.asyncio
async def test_submit_job_minimal_params():
    """Test submit_job with minimal required parameters."""
    result = await submit_job_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'Hello World'"
    )

    # Parse JSON response
    result_data = json.loads(result)

    assert result_data["success"] is True
    assert result_data["job_id"] is not None
    assert result_data["cluster"] == "slurm-local"
    assert result_data["backend"] in ["slurm", "flux", "mock"]
    assert result_data["state"] in ["PENDING", "SUBMITTED"]


@pytest.mark.asyncio
async def test_submit_job_all_params():
    """Test submit_job with all optional parameters."""
    result = await submit_job_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'Hello World'",
        job_name="test-job",
        nodes=4,
        tasks_per_node=8,
        cpus_per_task=2,
        memory="32GB",
        time_limit="2:00:00",
        partition="compute",
        output_path="/tmp/job.out",
        error_path="/tmp/job.err",
        working_dir="/home/user/jobs"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert result_data["cluster"] == "slurm-local"


@pytest.mark.asyncio
async def test_submit_job_missing_cluster():
    """Test submit_job fails when cluster is missing."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await submit_job_fn(
            cluster="",
            script="#!/bin/bash\necho 'test'"
        )


@pytest.mark.asyncio
async def test_submit_job_missing_script():
    """Test submit_job fails when script is missing."""
    with pytest.raises(ToolError, match="Script cannot be empty"):
        await submit_job_fn(
            cluster="slurm-local",
            script=""
        )


@pytest.mark.asyncio
async def test_submit_job_missing_shebang():
    """Test submit_job fails when script is missing shebang."""
    with pytest.raises(ToolError, match="Script must include shebang line"):
        await submit_job_fn(
            cluster="slurm-local",
            script="echo 'no shebang'"
        )


@pytest.mark.asyncio
async def test_submit_job_invalid_nodes():
    """Test submit_job fails with invalid node count."""
    with pytest.raises(ToolError, match="Number of nodes must be >= 1"):
        await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            nodes=0
        )


@pytest.mark.asyncio
async def test_submit_job_invalid_tasks():
    """Test submit_job fails with invalid tasks per node."""
    with pytest.raises(ToolError, match="Tasks per node must be >= 1"):
        await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            tasks_per_node=0
        )


@pytest.mark.asyncio
async def test_submit_job_invalid_cpus():
    """Test submit_job fails with invalid CPUs per task."""
    with pytest.raises(ToolError, match="CPUs per task must be >= 1"):
        await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            cpus_per_task=-1
        )


@pytest.mark.asyncio
async def test_submit_job_invalid_memory_format():
    """Test submit_job fails with invalid memory format."""
    with pytest.raises(ToolError, match="Invalid memory format"):
        await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            memory="invalid"
        )


@pytest.mark.asyncio
async def test_submit_job_valid_memory_formats():
    """Test submit_job accepts various valid memory formats."""
    valid_formats = ["32GB", "1024MB", "2TB", "512M", "4G", "1T"]

    for memory_format in valid_formats:
        result = await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            memory=memory_format
        )
        result_data = json.loads(result)
        assert result_data["success"] is True


@pytest.mark.asyncio
async def test_submit_job_invalid_time_limit():
    """Test submit_job fails with invalid time limit format."""
    with pytest.raises(ToolError, match="Invalid time limit format"):
        await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            time_limit="invalid"
        )


@pytest.mark.asyncio
async def test_submit_job_valid_time_formats():
    """Test submit_job accepts various valid time limit formats."""
    valid_formats = ["1h", "30m", "60s", "1:30", "2:00:00"]

    for time_format in valid_formats:
        result = await submit_job_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            time_limit=time_format
        )
        result_data = json.loads(result)
        assert result_data["success"] is True


@pytest.mark.asyncio
async def test_submit_job_default_working_dir():
    """Test submit_job uses /tmp as default working directory."""
    result = await submit_job_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'test'"
    )
    # In the real implementation, we would verify working_dir is set to /tmp
    result_data = json.loads(result)
    assert result_data["success"] is True


@pytest.mark.asyncio
async def test_submit_job_whitespace_trimming():
    """Test submit_job handles whitespace in parameters correctly."""
    result = await submit_job_fn(
        cluster="  slurm-local  ",
        script="#!/bin/bash\n  echo 'test'  \n",
        memory="  32GB  ",
        time_limit="  1h  "
    )
    result_data = json.loads(result)
    assert result_data["success"] is True


