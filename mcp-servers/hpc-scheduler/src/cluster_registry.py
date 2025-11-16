"""Cluster registry for managing HPC backend adapters"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from backends.base import BackendAdapter
from backends.slurm_adapter import SlurmAdapter
from backends.flux_adapter import FluxAdapter
from backends.mock_adapter import MockAdapter


class ClusterRegistry:
    """Registry for managing cluster configurations and backend adapters"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize cluster registry

        Args:
            config_path: Optional path to clusters.yaml config file.
                        If not provided, uses CLUSTERS_CONFIG env var or default path
        """
        self.adapters: Dict[str, BackendAdapter] = {}
        self.configs: Dict[str, Dict[str, Any]] = {}

        # Determine config file path
        if config_path is None:
            config_path = os.getenv("CLUSTERS_CONFIG", "config/clusters.yaml")

        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        """Load cluster configurations from YAML file"""
        config_file = Path(self.config_path)

        if not config_file.exists():
            # Use default configuration if file doesn't exist
            self._load_default_config()
            return

        try:
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)

            clusters = data.get("clusters", [])
            for cluster_config in clusters:
                name = cluster_config.get("name")
                if not name:
                    continue
                self.configs[name] = cluster_config

        except Exception as e:
            raise Exception(f"Failed to load cluster config from {config_file}: {e}")

    def _load_default_config(self):
        """Load default cluster configurations for local development"""
        # Default configs matching bootstrap setup
        default_clusters = [
            {
                "name": "slurm-local",
                "type": "slurm",
                "endpoint": "http://slurm-restapi.slurm.svc.cluster.local:6820",
                "namespace": "slurm",
                "auth": {"user": "slurm", "jwt_auto_generate": True},
            },
            {
                "name": "flux-local",
                "type": "flux",
                "namespace": "flux-operator",
                "minicluster": "flux-sample",
                "flux_uri": "local:///mnt/flux/view/run/flux/local",
            },
        ]

        for cluster_config in default_clusters:
            name = cluster_config["name"]
            self.configs[name] = cluster_config

    def get_adapter(self, cluster_name: str) -> BackendAdapter:
        """
        Get backend adapter for a cluster

        Args:
            cluster_name: Name of the cluster

        Returns:
            BackendAdapter instance

        Raises:
            Exception: If cluster not found or adapter creation fails
        """
        # Return cached adapter if exists
        if cluster_name in self.adapters:
            return self.adapters[cluster_name]

        # Get cluster config
        if cluster_name not in self.configs:
            available = ", ".join(self.configs.keys())
            raise Exception(
                f"Cluster '{cluster_name}' not found. Available clusters: {available}"
            )

        config = self.configs[cluster_name]
        cluster_type = config.get("type")

        # Check if mock backends are enabled
        use_mock = os.getenv("USE_MOCK_BACKENDS", "false").lower() == "true"

        # Create appropriate adapter
        if use_mock:
            # Use mock adapter with type hint for realistic behavior
            config["mock_type"] = cluster_type
            adapter = MockAdapter(config)
        elif cluster_type == "slurm":
            adapter = SlurmAdapter(config)
        elif cluster_type == "flux":
            adapter = FluxAdapter(config)
        elif cluster_type == "mock":
            # Explicitly configured as mock
            adapter = MockAdapter(config)
        else:
            raise Exception(
                f"Unknown cluster type '{cluster_type}' for cluster '{cluster_name}'"
            )

        # Cache adapter
        self.adapters[cluster_name] = adapter
        return adapter

    def list_clusters(self) -> Dict[str, str]:
        """
        List all configured clusters

        Returns:
            Dict mapping cluster name to backend type
        """
        return {name: config.get("type", "unknown") for name, config in self.configs.items()}

    def get_cluster_info(self, cluster_name: str) -> Dict[str, Any]:
        """
        Get configuration info for a cluster

        Args:
            cluster_name: Name of the cluster

        Returns:
            Dict with cluster configuration (without sensitive data)

        Raises:
            Exception: If cluster not found
        """
        if cluster_name not in self.configs:
            raise Exception(f"Cluster '{cluster_name}' not found")

        config = self.configs[cluster_name].copy()

        # Remove sensitive data
        if "auth" in config:
            auth = config["auth"].copy()
            if "jwt_token" in auth:
                auth["jwt_token"] = "***"
            config["auth"] = auth

        return config

    async def close_all(self):
        """Close all adapter connections"""
        for adapter in self.adapters.values():
            await adapter.close()
        self.adapters.clear()


# Global registry instance
_registry: Optional[ClusterRegistry] = None


def get_registry() -> ClusterRegistry:
    """
    Get global cluster registry instance

    Returns:
        ClusterRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ClusterRegistry()
    return _registry


def reset_registry():
    """Reset global registry (useful for testing)"""
    global _registry
    if _registry:
        import asyncio

        asyncio.create_task(_registry.close_all())
    _registry = None
