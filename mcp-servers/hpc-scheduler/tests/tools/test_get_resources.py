"""Tests for get_resources tool."""

import json
import pytest
from fastmcp.exceptions import ToolError
from src.tools.get_resources import get_resources

# Access the underlying function for testing (FastMCP decorator pattern)
get_resources_fn = get_resources.fn


@pytest.mark.asyncio
async def test_get_resources_concise_format():
    """Test get_resources with concise format (default)."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="concise"
    )

    # Parse JSON response
    result_data = json.loads(result)

    # Verify concise format fields
    assert result_data["success"] is True
    assert "nodes" in result_data
    assert "cores" in result_data

    # Verify nodes structure
    nodes = result_data["nodes"]
    assert "total" in nodes
    assert "idle" in nodes
    assert "allocated" in nodes
    assert "down" in nodes

    # Verify cores structure
    cores = result_data["cores"]
    assert "total" in cores
    assert "available" in cores

    # Ensure concise format does not include detailed fields
    assert "partitions" not in result_data
    assert "node_details" not in result_data


@pytest.mark.asyncio
async def test_get_resources_default_format():
    """Test get_resources defaults to concise format."""
    result = await get_resources_fn(cluster="slurm-local")

    result_data = json.loads(result)

    # Should behave like concise format
    assert result_data["success"] is True
    assert "nodes" in result_data
    assert "cores" in result_data
    assert "partitions" not in result_data
    assert "node_details" not in result_data


@pytest.mark.asyncio
async def test_get_resources_detailed_format():
    """Test get_resources with detailed format."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)

    # Verify all concise fields are present
    assert result_data["success"] is True
    assert "nodes" in result_data
    assert "cores" in result_data

    # Verify detailed-specific fields
    assert "partitions" in result_data
    assert "node_details" in result_data

    # Verify partitions structure
    partitions = result_data["partitions"]
    assert isinstance(partitions, list)
    assert len(partitions) > 0

    # Verify partition fields
    if partitions:
        partition = partitions[0]
        assert "name" in partition
        assert "state" in partition
        assert "nodes" in partition
        assert "max_time_limit" in partition
        assert "default_memory_per_cpu" in partition

    # Verify node_details structure
    node_details = result_data["node_details"]
    assert isinstance(node_details, list)
    assert len(node_details) > 0

    # Verify node detail fields
    if node_details:
        node = node_details[0]
        assert "name" in node
        assert "state" in node
        assert "cpus" in node
        assert "memory" in node
        assert "partitions" in node


@pytest.mark.asyncio
async def test_get_resources_numeric_values():
    """Test that numeric fields are integers."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="concise"
    )

    result_data = json.loads(result)

    # Verify node counts are integers
    nodes = result_data["nodes"]
    assert isinstance(nodes["total"], int)
    assert isinstance(nodes["idle"], int)
    assert isinstance(nodes["allocated"], int)
    assert isinstance(nodes["down"], int)

    # Verify core counts are integers
    cores = result_data["cores"]
    assert isinstance(cores["total"], int)
    assert isinstance(cores["available"], int)


@pytest.mark.asyncio
async def test_get_resources_non_negative_counts():
    """Test that resource counts are non-negative."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="concise"
    )

    result_data = json.loads(result)

    # All node counts should be >= 0
    nodes = result_data["nodes"]
    assert nodes["total"] >= 0
    assert nodes["idle"] >= 0
    assert nodes["allocated"] >= 0
    assert nodes["down"] >= 0

    # All core counts should be >= 0
    cores = result_data["cores"]
    assert cores["total"] >= 0
    assert cores["available"] >= 0


@pytest.mark.asyncio
async def test_get_resources_node_state_sum():
    """Test that node states sum correctly."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="concise"
    )

    result_data = json.loads(result)
    nodes = result_data["nodes"]

    # idle + allocated + down should equal total
    assert nodes["idle"] + nodes["allocated"] + nodes["down"] == nodes["total"]


@pytest.mark.asyncio
async def test_get_resources_missing_cluster():
    """Test get_resources fails when cluster is empty."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_resources_fn(cluster="")


@pytest.mark.asyncio
async def test_get_resources_whitespace_cluster():
    """Test get_resources fails when cluster is whitespace."""
    with pytest.raises(ToolError, match="Cluster name cannot be empty"):
        await get_resources_fn(cluster="   ")


@pytest.mark.asyncio
async def test_get_resources_invalid_format():
    """Test get_resources fails with invalid response_format."""
    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_resources_fn(
            cluster="slurm-local",
            response_format="invalid"
        )


@pytest.mark.asyncio
async def test_get_resources_flux_cluster():
    """Test get_resources works with flux-local cluster."""
    result = await get_resources_fn(
        cluster="flux-local",
        response_format="concise"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "nodes" in result_data
    assert "cores" in result_data


@pytest.mark.asyncio
async def test_get_resources_flux_detailed():
    """Test get_resources detailed format with Flux cluster."""
    result = await get_resources_fn(
        cluster="flux-local",
        response_format="detailed"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True

    # Flux should have partitions in detailed mode
    assert "partitions" in result_data
    partitions = result_data["partitions"]
    assert isinstance(partitions, list)


@pytest.mark.asyncio
async def test_get_resources_whitespace_trimming():
    """Test get_resources handles whitespace in cluster parameter."""
    result = await get_resources_fn(
        cluster="  slurm-local  ",
        response_format="concise"
    )

    result_data = json.loads(result)
    assert result_data["success"] is True


@pytest.mark.asyncio
async def test_get_resources_case_sensitive_format():
    """Test that response_format validation is case-sensitive."""
    # These should fail (case-sensitive validation)
    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_resources_fn(
            cluster="slurm-local",
            response_format="Concise"
        )

    with pytest.raises(ToolError, match="Invalid response_format"):
        await get_resources_fn(
            cluster="slurm-local",
            response_format="DETAILED"
        )


@pytest.mark.asyncio
async def test_get_resources_partition_states():
    """Test that partitions have valid states in detailed format."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)
    partitions = result_data["partitions"]

    # Check partition states are valid (UP or DOWN)
    for partition in partitions:
        assert partition["state"] in ["UP", "DOWN"]


@pytest.mark.asyncio
async def test_get_resources_node_states():
    """Test that nodes have valid states in detailed format."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="detailed"
    )

    result_data = json.loads(result)
    node_details = result_data["node_details"]

    # Check node states are valid
    valid_states = ["IDLE", "ALLOCATED", "MIXED", "DOWN"]
    for node in node_details:
        assert node["state"] in valid_states


@pytest.mark.asyncio
async def test_get_resources_cores_calculation():
    """Test that total cores makes sense relative to available cores."""
    result = await get_resources_fn(
        cluster="slurm-local",
        response_format="concise"
    )

    result_data = json.loads(result)
    cores = result_data["cores"]

    # Available cores should not exceed total cores
    assert cores["available"] <= cores["total"]
