import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

# Ensure we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.analyze_job import analyze_job
from cluster_registry import reset_registry


# Access the underlying function from the FastMCP decorator
analyze_job_fn = analyze_job.fn


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
async def test_analyze_job_cpu_intensive():
    """Test analysis of CPU-intensive script"""
    script = """#!/bin/bash
#SBATCH --job-name=mpi-test
mpirun -n 16 ./my_mpi_program
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["cluster"] == "slurm-local"
    assert result["backend"] == "slurm"

    # Check analysis
    analysis = result["analysis"]
    assert analysis["cpu_intensive"] is True
    assert analysis["recommended_nodes"] >= 1
    assert analysis["recommended_tasks"] >= 1
    assert "estimated_memory" in analysis
    assert "estimated_runtime" in analysis

    # Check recommendations
    assert len(result["recommendations"]) >= 4
    assert any(r["parameter"] == "nodes" for r in result["recommendations"])
    assert any(r["parameter"] == "tasks" for r in result["recommendations"])
    assert any(r["parameter"] == "memory" for r in result["recommendations"])
    assert any(r["parameter"] == "time_limit" for r in result["recommendations"])

    # Check historical comparison (no historical_job_id provided)
    historical = result["historical_comparison"]
    assert historical["similar_jobs"] == 0
    assert historical["avg_runtime"] == "N/A"


@pytest.mark.asyncio
async def test_analyze_job_memory_intensive():
    """Test analysis of memory-intensive script"""
    script = """#!/bin/bash
#SBATCH --job-name=memory-test
python process_large_array.py
# Process 64GB dataset
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    analysis = result["analysis"]
    assert analysis["memory_intensive"] is True

    # Memory intensive workloads should have higher memory estimates
    assert "GB" in analysis["estimated_memory"]


@pytest.mark.asyncio
async def test_analyze_job_io_intensive():
    """Test analysis of I/O-intensive script"""
    script = """#!/bin/bash
#SBATCH --job-name=io-test
dd if=/dev/zero of=/data/output.bin bs=1M count=10000
rsync -av /mnt/source/ /mnt/destination/
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    analysis = result["analysis"]
    assert analysis["io_intensive"] is True

    # Should have I/O-specific recommendation
    recommendations = result["recommendations"]
    io_rec = [r for r in recommendations if r["parameter"] == "partition"]
    assert len(io_rec) > 0
    assert "io-optimized" in io_rec[0]["value"]


@pytest.mark.asyncio
async def test_analyze_job_generic_workload():
    """Test analysis of generic script"""
    script = """#!/bin/bash
#SBATCH --job-name=simple-test
echo "Hello, World!"
./simple_program
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    analysis = result["analysis"]

    # Generic workload should have conservative estimates
    assert analysis["cpu_intensive"] is False
    assert analysis["memory_intensive"] is False
    assert analysis["io_intensive"] is False
    assert analysis["recommended_nodes"] == 1
    assert analysis["recommended_tasks"] == 1


@pytest.mark.asyncio
async def test_analyze_job_with_historical():
    """Test analysis with historical job reference"""
    script = """#!/bin/bash
#SBATCH --job-name=test
echo "Test job"
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
        historical_job_id="12345",
    )

    result = json.loads(result_json)

    assert result["success"] is True

    # Check historical comparison
    historical = result["historical_comparison"]
    assert historical["similar_jobs"] > 0
    assert historical["avg_runtime"] != "N/A"
    assert historical["avg_memory"] != "N/A"
    assert 0.0 <= historical["success_rate"] <= 1.0


@pytest.mark.asyncio
async def test_analyze_job_empty_cluster():
    """Test that empty cluster name raises ToolError"""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await analyze_job_fn(
            cluster="",
            script="#!/bin/bash\necho 'test'",
        )


@pytest.mark.asyncio
async def test_analyze_job_empty_script():
    """Test that empty script raises ToolError"""
    with pytest.raises(ToolError, match="Script cannot be empty"):
        await analyze_job_fn(
            cluster="slurm-local",
            script="",
        )


@pytest.mark.asyncio
async def test_analyze_job_no_shebang():
    """Test that script without shebang raises ToolError"""
    with pytest.raises(ToolError, match="Script must include shebang"):
        await analyze_job_fn(
            cluster="slurm-local",
            script="echo 'missing shebang'",
        )


@pytest.mark.asyncio
async def test_analyze_job_invalid_cluster():
    """Test that invalid cluster raises ToolError"""
    with pytest.raises(ToolError, match="Cluster validation failed"):
        await analyze_job_fn(
            cluster="nonexistent-cluster",
            script="#!/bin/bash\necho 'test'",
        )


@pytest.mark.asyncio
async def test_analyze_job_flux_cluster():
    """Test analysis on flux cluster"""
    script = """#!/bin/bash
#FLUX: --job-name=test
flux run -n 4 ./my_program
"""

    result_json = await analyze_job_fn(
        cluster="flux-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["cluster"] == "flux-local"
    assert result["backend"] == "flux"


@pytest.mark.asyncio
async def test_analyze_job_mpi_task_detection():
    """Test MPI task count detection"""
    script = """#!/bin/bash
#SBATCH --job-name=mpi-test
mpirun -n 16 ./my_program
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    analysis = result["analysis"]

    # Should detect MPI and recommend tasks based on -n flag
    assert analysis["cpu_intensive"] is True
    assert analysis["recommended_tasks"] == 16


@pytest.mark.asyncio
async def test_analyze_job_recommendation_confidence():
    """Test that recommendations include confidence levels"""
    script = """#!/bin/bash
#SBATCH --job-name=test
mpirun -n 8 ./cpu_program
"""

    result_json = await analyze_job_fn(
        cluster="slurm-local",
        script=script,
    )

    result = json.loads(result_json)

    assert result["success"] is True
    recommendations = result["recommendations"]

    # All recommendations should have required fields
    for rec in recommendations:
        assert "parameter" in rec
        assert "value" in rec
        assert "confidence" in rec
        assert rec["confidence"] in ["high", "medium", "low"]
        assert "reason" in rec
        assert len(rec["reason"]) > 0
