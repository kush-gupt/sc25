"""Tests for submit_batch tool."""

import os
import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.submit_batch import submit_batch
from src.cluster_registry import reset_registry

# Access the underlying function for testing (FastMCP decorator pattern)
submit_batch_fn = submit_batch.fn


@pytest.fixture(autouse=True)
def setup_mock_env():
    """Setup mock environment for all tests"""
    os.environ["USE_MOCK_BACKENDS"] = "true"
    yield
    reset_registry()
    # Clean up
    if "USE_MOCK_BACKENDS" in os.environ:
        del os.environ["USE_MOCK_BACKENDS"]


@pytest.mark.asyncio
async def test_submit_batch_slurm_array():
    """Test Slurm array job submission."""
    result = await submit_batch_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'Task $SLURM_ARRAY_TASK_ID'",
        array_spec="1-10",
        response_format="concise",
    )

    # Parse JSON result
    data = json.loads(result)

    # Assertions
    assert data["success"] is True
    assert data["batch_type"] == "array"
    assert data["submitted"] > 0
    assert data["failed"] == 0
    assert len(data["job_ids"]) > 0
    assert "errors" not in data or len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_submit_batch_slurm_array_with_step():
    """Test Slurm array job with step specification."""
    result = await submit_batch_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'Running task $SLURM_ARRAY_TASK_ID'",
        array_spec="1-100:2",
        job_name_prefix="sweep",
        nodes=2,
        tasks_per_node=4,
        time_limit="01:00:00",
        response_format="concise",
    )

    data = json.loads(result)
    assert data["success"] is True
    assert data["batch_type"] == "array"
    assert data["submitted"] > 0


@pytest.mark.asyncio
async def test_submit_batch_slurm_array_with_max_concurrent():
    """Test Slurm array job with max concurrent limit."""
    result = await submit_batch_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'Task $SLURM_ARRAY_TASK_ID'",
        array_spec="1-50",
        max_concurrent=10,
        response_format="detailed",
    )

    data = json.loads(result)
    assert data["success"] is True
    assert data["batch_type"] == "array"
    # Should respect max_concurrent if implemented


@pytest.mark.asyncio
async def test_submit_batch_flux_bulk():
    """Test Flux bulk job submission."""
    commands = [
        "echo 'Job 1'",
        "echo 'Job 2'",
        "echo 'Job 3'",
    ]

    result = await submit_batch_fn(
        cluster="flux-local",
        script="#!/bin/bash",
        commands=commands,
        job_name_prefix="bulk",
        response_format="concise",
    )

    data = json.loads(result)
    assert data["success"] is True
    assert data["batch_type"] == "bulk"
    assert data["submitted"] == len(commands)
    assert data["failed"] == 0
    assert len(data["job_ids"]) == len(commands)


@pytest.mark.asyncio
async def test_submit_batch_flux_bulk_with_resources():
    """Test Flux bulk submission with resource specifications."""
    commands = [
        "python simulation.py --param=1",
        "python simulation.py --param=2",
    ]

    result = await submit_batch_fn(
        cluster="flux-local",
        script="#!/bin/bash",
        commands=commands,
        job_name_prefix="sim",
        nodes=1,
        tasks_per_node=2,
        time_limit="00:30:00",
        response_format="detailed",
    )

    data = json.loads(result)
    assert data["success"] is True
    assert data["batch_type"] == "bulk"
    assert data["submitted"] == 2


@pytest.mark.asyncio
async def test_submit_batch_empty_cluster():
    """Test error handling for empty cluster name."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await submit_batch_fn(
            cluster="",
            script="#!/bin/bash\necho 'test'",
            array_spec="1-5",
        )


@pytest.mark.asyncio
async def test_submit_batch_empty_script():
    """Test error handling for empty script."""
    with pytest.raises(ToolError, match="Script cannot be empty"):
        await submit_batch_fn(
            cluster="slurm-local",
            script="",
            array_spec="1-5",
        )


@pytest.mark.asyncio
async def test_submit_batch_missing_array_and_commands():
    """Test error when neither array_spec nor commands provided."""
    with pytest.raises(
        ToolError,
        match="Either array_spec \\(for Slurm\\) or commands \\(for Flux\\) must be provided",
    ):
        await submit_batch_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
        )


@pytest.mark.asyncio
async def test_submit_batch_both_array_and_commands():
    """Test error when both array_spec and commands provided."""
    with pytest.raises(
        ToolError,
        match="Cannot specify both array_spec and commands - use one or the other",
    ):
        await submit_batch_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            array_spec="1-5",
            commands=["echo 'test'"],
        )


@pytest.mark.asyncio
async def test_submit_batch_invalid_response_format():
    """Test error handling for invalid response format."""
    with pytest.raises(ToolError, match="response_format must be 'concise' or 'detailed'"):
        await submit_batch_fn(
            cluster="slurm-local",
            script="#!/bin/bash\necho 'test'",
            array_spec="1-5",
            response_format="invalid",
        )


@pytest.mark.asyncio
async def test_submit_batch_unknown_cluster():
    """Test error handling for unknown cluster."""
    with pytest.raises(ToolError, match="Failed to submit batch jobs"):
        await submit_batch_fn(
            cluster="unknown-cluster",
            script="#!/bin/bash\necho 'test'",
            array_spec="1-5",
        )


@pytest.mark.asyncio
async def test_submit_batch_concise_format():
    """Test concise response format."""
    result = await submit_batch_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'test'",
        array_spec="1-5",
        response_format="concise",
    )

    data = json.loads(result)
    # Verify concise format has only key fields
    assert "success" in data
    assert "job_ids" in data
    assert "batch_type" in data
    assert "submitted" in data
    assert "failed" in data


@pytest.mark.asyncio
async def test_submit_batch_detailed_format():
    """Test detailed response format."""
    result = await submit_batch_fn(
        cluster="slurm-local",
        script="#!/bin/bash\necho 'test'",
        array_spec="1-5",
        response_format="detailed",
    )

    data = json.loads(result)
    # Verify detailed format has all fields
    assert "success" in data
    assert "job_ids" in data
    assert "batch_type" in data
    assert "submitted" in data
    assert "failed" in data
    assert "errors" in data
