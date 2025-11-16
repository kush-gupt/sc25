import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

# Ensure we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.cancel_job import cancel_job
from cluster_registry import reset_registry


# Access the underlying function from the FastMCP decorator
cancel_job_fn = cancel_job.fn


@pytest.fixture(autouse=True)
async def setup_mock_env(monkeypatch):
    """Set up mock backend environment for all tests"""
    monkeypatch.setenv("USE_MOCK_BACKENDS", "true")
    # Reset registry before each test to ensure clean state
    reset_registry()
    yield
    # Clean up registry after test
    from cluster_registry import _registry
    if _registry:
        await _registry.close_all()
    reset_registry()


@pytest.mark.asyncio
async def test_cancel_job_success():
    """Test successful job cancellation"""
    result_json = await cancel_job_fn(
        cluster="slurm-local",
        job_id="12345",
        signal="TERM"
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["job_id"] == "12345"
    assert result["state"] == "CANCELLED"
    assert "message" in result


@pytest.mark.asyncio
async def test_cancel_job_default_signal():
    """Test job cancellation with default TERM signal"""
    result_json = await cancel_job_fn(
        cluster="slurm-local",
        job_id="12345"
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["job_id"] == "12345"
    assert result["state"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_job_kill_signal():
    """Test job cancellation with KILL signal"""
    result_json = await cancel_job_fn(
        cluster="slurm-local",
        job_id="12345",
        signal="KILL"
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["job_id"] == "12345"
    assert result["state"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_job_int_signal():
    """Test job cancellation with INT signal"""
    result_json = await cancel_job_fn(
        cluster="slurm-local",
        job_id="12345",
        signal="INT"
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["job_id"] == "12345"
    assert result["state"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_job_empty_cluster():
    """Test that empty cluster name raises ToolError"""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await cancel_job_fn(
            cluster="",
            job_id="12345",
            signal="TERM"
        )


@pytest.mark.asyncio
async def test_cancel_job_empty_job_id():
    """Test that empty job ID raises ToolError"""
    with pytest.raises(ToolError, match="Job ID cannot be empty"):
        await cancel_job_fn(
            cluster="slurm-local",
            job_id="",
            signal="TERM"
        )


@pytest.mark.asyncio
async def test_cancel_job_invalid_signal():
    """Test that invalid signal raises ToolError"""
    with pytest.raises(ToolError, match="Invalid signal 'INVALID'"):
        await cancel_job_fn(
            cluster="slurm-local",
            job_id="12345",
            signal="INVALID"
        )


@pytest.mark.asyncio
async def test_cancel_job_invalid_cluster():
    """Test that invalid cluster name returns error result"""
    result_json = await cancel_job_fn(
        cluster="nonexistent-cluster",
        job_id="12345",
        signal="TERM"
    )

    result = json.loads(result_json)

    assert result["success"] is False
    assert result["job_id"] == "12345"
    assert result["state"] == "UNKNOWN"
    assert "error" in result
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_cancel_job_flux_cluster():
    """Test job cancellation on flux cluster"""
    result_json = await cancel_job_fn(
        cluster="flux-local",
        job_id="67890",
        signal="TERM"
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["job_id"] == "67890"
    assert result["state"] == "CANCELLED"
