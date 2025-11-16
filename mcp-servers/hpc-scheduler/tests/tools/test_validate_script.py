import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

# Ensure we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.validate_script import validate_script
from cluster_registry import reset_registry


# Access the underlying function from the FastMCP decorator
validate_script_fn = validate_script.fn


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
async def test_validate_script_success():
    """Test successful script validation"""
    script = """#!/bin/bash
#SBATCH --job-name=test
#SBATCH --nodes=1

echo "Hello, World!"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script,
        nodes=1,
        time_limit="1h",
        partition=None
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["valid"] is True
    assert "issues" in result
    assert "recommendations" in result


@pytest.mark.asyncio
async def test_validate_script_missing_shebang():
    """Test validation catches missing shebang"""
    script = """echo "No shebang!"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["valid"] is False
    assert len(result["issues"]) > 0

    # Find the shebang error
    shebang_issue = next((i for i in result["issues"] if i["category"] == "syntax" and "shebang" in i["message"].lower()), None)
    assert shebang_issue is not None
    assert shebang_issue["severity"] == "error"
    assert shebang_issue["line"] == 1


@pytest.mark.asyncio
async def test_validate_script_invalid_nodes():
    """Test validation catches invalid node count"""
    script = """#!/bin/bash
echo "Test"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script,
        nodes=0
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["valid"] is False

    # Find the nodes error
    nodes_issue = next((i for i in result["issues"] if "Node count must be >= 1" in i["message"]), None)
    assert nodes_issue is not None
    assert nodes_issue["severity"] == "error"
    assert nodes_issue["category"] == "resources"


@pytest.mark.asyncio
async def test_validate_script_nodes_exceed_cluster():
    """Test validation catches node count exceeding cluster capacity"""
    script = """#!/bin/bash
echo "Test"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script,
        nodes=1000  # Way more than any cluster has
    )

    result = json.loads(result_json)

    assert result["success"] is True
    # Should have error about exceeding cluster capacity
    assert len(result["issues"]) > 0
    assert len(result["recommendations"]) > 0

    # Find the nodes recommendation
    nodes_rec = next((r for r in result["recommendations"] if r["field"] == "nodes"), None)
    assert nodes_rec is not None
    assert nodes_rec["reason"] == "Cluster maximum"


@pytest.mark.asyncio
async def test_validate_script_invalid_time_format():
    """Test validation catches invalid time format"""
    script = """#!/bin/bash
echo "Test"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script,
        time_limit="invalid"
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert result["valid"] is False

    # Find the time format error
    time_issue = next((i for i in result["issues"] if "Invalid time limit format" in i["message"]), None)
    assert time_issue is not None
    assert time_issue["severity"] == "error"
    assert time_issue["category"] == "syntax"


@pytest.mark.asyncio
async def test_validate_script_valid_time_formats():
    """Test validation accepts various valid time formats"""
    script = """#!/bin/bash
echo "Test"
"""

    valid_formats = ["1h", "30m", "60s", "1:30", "2:30:00"]

    for time_format in valid_formats:
        result_json = await validate_script_fn(
            cluster="slurm-local",
            script=script,
            time_limit=time_format
        )

        result = json.loads(result_json)

        assert result["success"] is True
        # Should not have time format errors
        time_errors = [i for i in result["issues"] if "Invalid time limit format" in i["message"]]
        assert len(time_errors) == 0


@pytest.mark.asyncio
async def test_validate_script_empty_script():
    """Test validation catches empty script"""
    script = """#!/bin/bash
# Only comments
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script
    )

    result = json.loads(result_json)

    assert result["success"] is True

    # Should have warning about no executable commands
    warning = next((i for i in result["issues"] if "no executable commands" in i["message"].lower()), None)
    assert warning is not None
    assert warning["severity"] == "warning"


@pytest.mark.asyncio
async def test_validate_script_module_load_warning():
    """Test validation warns about module load"""
    script = """#!/bin/bash
module load gcc/11.2.0
echo "Test"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script
    )

    result = json.loads(result_json)

    assert result["success"] is True

    # Should have info about module load
    info = next((i for i in result["issues"] if "module load" in i["message"].lower()), None)
    assert info is not None
    assert info["severity"] == "info"
    assert info["category"] == "compatibility"


@pytest.mark.asyncio
async def test_validate_script_empty_cluster():
    """Test that empty cluster name raises ToolError"""
    script = """#!/bin/bash
echo "Test"
"""

    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await validate_script_fn(
            cluster="",
            script=script
        )


@pytest.mark.asyncio
async def test_validate_script_empty_script_parameter():
    """Test that empty script raises ToolError"""
    with pytest.raises(ToolError, match="Script cannot be empty"):
        await validate_script_fn(
            cluster="slurm-local",
            script=""
        )


@pytest.mark.asyncio
async def test_validate_script_optional_parameters():
    """Test validation with only required parameters"""
    script = """#!/bin/bash
echo "Test"
"""

    result_json = await validate_script_fn(
        cluster="slurm-local",
        script=script
    )

    result = json.loads(result_json)

    assert result["success"] is True
    assert "issues" in result
    assert "recommendations" in result


@pytest.mark.asyncio
async def test_validate_script_flux_cluster():
    """Test validation works with flux cluster"""
    script = """#!/bin/bash
echo "Test"
"""

    result_json = await validate_script_fn(
        cluster="flux-local",
        script=script,
        nodes=1
    )

    result = json.loads(result_json)

    assert result["success"] is True
    # Flux doesn't have partitions, so partition validation shouldn't apply


@pytest.mark.asyncio
async def test_validate_script_invalid_cluster():
    """Test validation with invalid cluster name"""
    script = """#!/bin/bash
echo "Test"
"""

    with pytest.raises(ToolError, match="Failed to get cluster information"):
        await validate_script_fn(
            cluster="nonexistent-cluster",
            script=script
        )
