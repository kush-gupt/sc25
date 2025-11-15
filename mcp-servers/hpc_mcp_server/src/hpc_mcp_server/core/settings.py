"""Configuration helpers for the unified MCP server."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field, field_validator


class SlurmSettings(BaseModel):
    rest_url: str = Field(default="http://slurm-restapi.slurm.svc.cluster.local:6820")
    user: str = Field(default="slurm")
    namespace: str = Field(default="slurm")


class FluxSettings(BaseModel):
    namespace: str = Field(default="flux-operator")
    minicluster: str = Field(default="flux-sample")
    kubeconfig: str | None = Field(default=None)


class ServerSettings(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=5000)
    transport: str = Field(default_factory=lambda: os.getenv("MCP_TRANSPORT", "http"))


class Settings(BaseModel):
    slurm: SlurmSettings = Field(default_factory=SlurmSettings)
    flux: FluxSettings = Field(default_factory=FluxSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    allow_namespaces: list[str] = Field(default_factory=list)

    @field_validator("allow_namespaces", mode="before")
    @classmethod
    def _parse_namespaces(cls, value):
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return value


def load_settings() -> Settings:
    """Load settings from environment variables."""
    allowed_ns = os.getenv("ALLOWED_NAMESPACES")
    return Settings(
        slurm=SlurmSettings(
            rest_url=os.getenv("SLURM_REST_URL", SlurmSettings().rest_url),
            user=os.getenv("SLURM_USER", SlurmSettings().user),
            namespace=os.getenv("SLURM_NAMESPACE", SlurmSettings().namespace),
        ),
        flux=FluxSettings(
            namespace=os.getenv("FLUX_NAMESPACE", FluxSettings().namespace),
            minicluster=os.getenv("FLUX_MINICLUSTER", FluxSettings().minicluster),
            kubeconfig=os.getenv("KUBECONFIG"),
        ),
        server=ServerSettings(
            host=os.getenv("MCP_HOST", ServerSettings().host),
            port=int(os.getenv("MCP_PORT", str(ServerSettings().port))),
            transport=os.getenv("MCP_TRANSPORT", ServerSettings().transport),
        ),
        allow_namespaces=allowed_ns if allowed_ns is not None else [],
    )
