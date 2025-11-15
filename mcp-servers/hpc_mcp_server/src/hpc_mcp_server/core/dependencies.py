"""Dependency helpers for lazily-instantiated clients/settings."""
from __future__ import annotations

from functools import lru_cache

from ..clients.flux_operator_client import FluxOperatorClient
from ..clients.slurm_client import SlurmClient
from .settings import Settings, load_settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_slurm_client() -> SlurmClient:
    settings = get_settings()
    return SlurmClient(
        base_url=settings.slurm.rest_url,
        namespace=settings.slurm.namespace,
    )


@lru_cache(maxsize=1)
def get_flux_client() -> FluxOperatorClient:
    settings = get_settings()
    return FluxOperatorClient(
        namespace=settings.flux.namespace,
        default_minicluster=settings.flux.minicluster,
        allowed_namespaces=settings.allow_namespaces,
        kubeconfig=settings.flux.kubeconfig,
    )
