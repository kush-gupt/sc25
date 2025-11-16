"""Tests for run_and_wait tool"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from fastmcp.exceptions import ToolError
from src.tools.run_and_wait import run_and_wait


# Access the underlying function
run_and_wait_fn = run_and_wait.fn


@pytest.mark.asyncio
async def test_run_and_wait_success():
    """Test successful job completion"""
    # Mock the tool functions
    with patch("tools.submit_job.submit_job") as mock_submit, \
         patch("tools.get_job.get_job") as mock_get_job, \
         patch("tools.get_job_output.get_job_output") as mock_output:

        # Setup mock submit_job
        mock_submit.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12345",
            "cluster": "test-cluster",
            "backend": "slurm",
            "state": "PENDING"
        }))

        # Setup mock get_job - returns COMPLETED on first call
        mock_get_job.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job": {
                "job_id": "12345",
                "name": "test-job",
                "state": "COMPLETED",
                "exit_code": 0,
                "runtime": "00:01:23",
                "submitted": "2025-01-01T12:00:00"
            }
        }))

        # Setup mock get_job_output
        mock_output.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12345",
            "stdout": "Job completed successfully",
            "stderr": "",
            "truncated": False
        }))

        # Execute
        result_str = await run_and_wait_fn(
            cluster="test-cluster",
            script="#!/bin/bash\necho 'test'",
            job_name="test-job",
            timeout_minutes=1,
            poll_interval=1
        )

        result = json.loads(result_str)

        # Assertions
        assert result["success"] is True
        assert result["job_id"] == "12345"
        assert result["state"] == "COMPLETED"
        assert result["exit_code"] == 0
        assert result["runtime"] == "00:01:23"
        assert result["stdout"] == "Job completed successfully"
        assert result["stderr"] == ""
        assert "error" not in result


@pytest.mark.asyncio
async def test_run_and_wait_job_failed():
    """Test job that fails"""
    with patch("tools.submit_job.submit_job") as mock_submit, \
         patch("tools.get_job.get_job") as mock_get_job, \
         patch("tools.get_job_output.get_job_output") as mock_output:

        mock_submit.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12346",
            "cluster": "test-cluster",
            "backend": "slurm",
            "state": "PENDING"
        }))

        mock_get_job.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job": {
                "job_id": "12346",
                "state": "FAILED",
                "exit_code": 1,
                "runtime": "00:00:05",
                "submitted": "2025-01-01T12:00:00"
            }
        }))

        mock_output.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12346",
            "stdout": "",
            "stderr": "Error: command not found",
            "truncated": False
        }))

        result_str = await run_and_wait_fn(
            cluster="test-cluster",
            script="#!/bin/bash\nexit 1",
            timeout_minutes=1,
            poll_interval=1
        )

        result = json.loads(result_str)

        assert result["success"] is False
        assert result["job_id"] == "12346"
        assert result["state"] == "FAILED"
        assert result["exit_code"] == 1
        assert result["stderr"] == "Error: command not found"
        assert "error" in result
        assert "FAILED" in result["error"]


@pytest.mark.asyncio
async def test_run_and_wait_timeout():
    """Test job that times out"""
    from datetime import datetime, timedelta

    with patch("tools.submit_job.submit_job") as mock_submit, \
         patch("tools.get_job.get_job") as mock_get_job, \
         patch("tools.get_job_output.get_job_output") as mock_output, \
         patch("asyncio.sleep", new_callable=AsyncMock):

        mock_submit.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12347",
            "cluster": "test-cluster",
            "backend": "slurm",
            "state": "PENDING"
        }))

        # Job stays in RUNNING state
        mock_get_job.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job": {
                "job_id": "12347",
                "state": "RUNNING",
                "exit_code": None,
                "runtime": "00:05:00",
                "submitted": "2025-01-01T12:00:00"
            }
        }))

        mock_output.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12347",
            "stdout": "Partial output...",
            "stderr": "",
            "truncated": False
        }))

        # Mock datetime to simulate timeout
        with patch("src.tools.run_and_wait.datetime") as mock_datetime:
            # First call (start_time): returns "now"
            # Second call (timeout_time calc): returns "now"
            # Third call (first while check): returns "now + 2 minutes" (past timeout)
            fake_start = datetime(2025, 1, 1, 12, 0, 0)
            fake_past_timeout = fake_start + timedelta(minutes=2)

            mock_datetime.now.side_effect = [fake_start, fake_past_timeout]
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result_str = await run_and_wait_fn(
                cluster="test-cluster",
                script="#!/bin/bash\nsleep 3600",
                timeout_minutes=1,  # 1 minute timeout
                poll_interval=1
            )

            result = json.loads(result_str)

            assert result["success"] is False
            assert result["job_id"] == "12347"
            assert result["state"] == "TIMEOUT"
            assert "error" in result
            assert "did not complete" in result["error"].lower()


@pytest.mark.asyncio
async def test_run_and_wait_submission_failed():
    """Test when job submission fails"""
    with patch("tools.submit_job.submit_job") as mock_submit:

        mock_submit.fn = AsyncMock(return_value=json.dumps({
            "success": False,
            "cluster": "test-cluster",
            "error": "Invalid cluster configuration"
        }))

        result_str = await run_and_wait_fn(
            cluster="invalid-cluster",
            script="#!/bin/bash\necho 'test'"
        )

        result = json.loads(result_str)

        assert result["success"] is False
        assert "error" in result
        assert "submission failed" in result["error"].lower()


@pytest.mark.asyncio
async def test_run_and_wait_empty_cluster():
    """Test validation: empty cluster name"""
    with pytest.raises(ToolError) as exc_info:
        await run_and_wait_fn(
            cluster="",
            script="#!/bin/bash\necho 'test'"
        )

    assert "cluster name cannot be empty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_run_and_wait_empty_script():
    """Test validation: empty script"""
    with pytest.raises(ToolError) as exc_info:
        await run_and_wait_fn(
            cluster="test-cluster",
            script=""
        )

    assert "script cannot be empty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_run_and_wait_invalid_timeout():
    """Test validation: invalid timeout_minutes"""
    with pytest.raises(ToolError) as exc_info:
        await run_and_wait_fn(
            cluster="test-cluster",
            script="#!/bin/bash\necho 'test'",
            timeout_minutes=0
        )

    assert "timeout_minutes must be >= 1" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_run_and_wait_invalid_poll_interval():
    """Test validation: invalid poll_interval"""
    with pytest.raises(ToolError) as exc_info:
        await run_and_wait_fn(
            cluster="test-cluster",
            script="#!/bin/bash\necho 'test'",
            poll_interval=0
        )

    assert "poll_interval must be >= 1" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_run_and_wait_with_all_parameters():
    """Test with all optional parameters specified"""
    with patch("tools.submit_job.submit_job") as mock_submit, \
         patch("tools.get_job.get_job") as mock_get_job, \
         patch("tools.get_job_output.get_job_output") as mock_output:

        mock_submit.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12348",
            "cluster": "test-cluster",
            "backend": "slurm",
            "state": "PENDING"
        }))

        mock_get_job.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job": {
                "job_id": "12348",
                "state": "COMPLETED",
                "exit_code": 0,
                "runtime": "00:02:15",
                "submitted": "2025-01-01T12:00:00"
            }
        }))

        mock_output.fn = AsyncMock(return_value=json.dumps({
            "success": True,
            "job_id": "12348",
            "stdout": "Success",
            "stderr": "",
            "truncated": False
        }))

        result_str = await run_and_wait_fn(
            cluster="test-cluster",
            script="#!/bin/bash\necho 'test'",
            job_name="full-param-test",
            nodes=2,
            tasks_per_node=4,
            time_limit="1h",
            timeout_minutes=30,
            poll_interval=5
        )

        result = json.loads(result_str)

        assert result["success"] is True
        assert result["job_id"] == "12348"
        assert result["state"] == "COMPLETED"

        # Verify submit_job was called with all parameters
        mock_submit.fn.assert_called_once()
        call_kwargs = mock_submit.fn.call_args.kwargs
        assert call_kwargs["cluster"] == "test-cluster"
        assert call_kwargs["job_name"] == "full-param-test"
        assert call_kwargs["nodes"] == 2
        assert call_kwargs["tasks_per_node"] == 4
        assert call_kwargs["time_limit"] == "1h"
