"""Flux MiniCluster oriented tool definitions."""
from __future__ import annotations

from typing import Dict

from pydantic import Field, PositiveInt

from ..core.app import mcp
from ..core.dependencies import get_flux_client
from ..clients.flux_operator_client import ContainerConfig, MiniClusterSpec


@mcp.tool(description="List MiniClusters managed by the Flux Operator")
def flux_list_miniclusters(
    namespace: str | None = Field(default=None, description="Override namespace (must be allowed)"),
) -> Dict:
    client = get_flux_client()
    return client.list_miniclusters(namespace=namespace)


@mcp.tool(description="Fetch a specific MiniCluster")
def flux_get_minicluster(
    name: str | None = Field(default=None, description="MiniCluster name"),
    namespace: str | None = Field(default=None, description="Namespace override"),
) -> Dict:
    client = get_flux_client()
    return client.get_minicluster(name=name, namespace=namespace)


@mcp.tool(description="Create or update a MiniCluster spec")
def flux_apply_minicluster(
    name: str = Field(..., description="MiniCluster name"),
    size: PositiveInt = Field(..., description="Number of pods"),
    container_image: str = Field(..., description="Primary workload image"),
    namespace: str | None = Field(default=None, description="Namespace override"),
    max_size: PositiveInt | None = Field(default=None, description="Maximum pods for elasticity"),
    tasks: int | None = Field(default=None, description="Tasks per pod"),
    command: str | None = Field(default=None, description="Command to run inside the container"),
    batch: bool = Field(default=False, description="Wrap command via flux batch"),
    environment: Dict[str, str] | None = Field(
        default=None, description="Environment variables for the container"
    ),
    wait_ready: bool = Field(default=False, description="Wait until MiniCluster is running"),
) -> Dict:
    if batch:
        if not command or not command.strip():
            raise ValueError("batch executions require a command to run via Flux")
        if tasks is None or tasks <= 0:
            raise ValueError("batch executions require a positive tasks value")

    container = ContainerConfig(
        image=container_image,
        command=command,
        tasks=tasks,
        batch=batch,
        environment=environment,
    )
    spec = MiniClusterSpec(
        size=size,
        maxSize=max_size,
        tasks=tasks,
        containers=[container],
    )
    client = get_flux_client()
    return client.apply_minicluster(
        spec=spec,
        name=name,
        namespace=namespace,
        wait_ready=wait_ready,
    )


@mcp.tool(description="Scale an existing MiniCluster")
def flux_scale_minicluster(
    name: str = Field(..., description="MiniCluster name"),
    size: PositiveInt = Field(..., description="New desired size"),
    namespace: str | None = Field(default=None, description="Namespace override"),
    max_size: PositiveInt | None = Field(default=None, description="Optional new max size"),
) -> Dict:
    client = get_flux_client()
    return client.scale_minicluster(size=size, name=name, namespace=namespace, max_size=max_size)


@mcp.tool(description="Delete a MiniCluster")
def flux_delete_minicluster(
    name: str = Field(description="MiniCluster name"),
    namespace: str | None = Field(default=None, description="Namespace override"),
) -> Dict:
    client = get_flux_client()
    return client.delete_minicluster(name=name, namespace=namespace)
