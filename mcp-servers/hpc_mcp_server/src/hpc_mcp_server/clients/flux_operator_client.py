"""Flux Operator MiniCluster client with secure helpers."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from kubernetes import client, config, watch
from kubernetes.config.config_exception import ConfigException
from pydantic import BaseModel, Field, PositiveInt, field_validator

logger = logging.getLogger(__name__)

GROUP = "flux-framework.org"
VERSION = "v1alpha2"
PLURAL = "miniclusters"


class ContainerConfig(BaseModel):
    """Subset of MiniCluster container config we support."""

    image: str = Field(description="Container image reference")
    name: str = Field(default="flux-runner")
    command: Optional[str] = Field(default=None)
    cores: Optional[int] = Field(default=None)
    tasks: Optional[int] = Field(default=None)
    runFlux: Optional[bool] = Field(default=True)
    batch: Optional[bool] = Field(default=False)
    environment: Dict[str, str] | None = None
    volumes: Dict[str, Dict[str, Any]] | None = None

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str) -> str:
        if ".." in value or value.strip() == "":
            raise ValueError("container image must be non-empty and sanitized")
        return value


class MiniClusterSpec(BaseModel):
    """Validated MiniCluster spec."""

    size: PositiveInt = Field(description="Number of pods to start")
    maxSize: Optional[PositiveInt] = Field(default=None)
    tasks: Optional[int] = Field(default=None, ge=0)
    interactive: Optional[bool] = None
    deadline: Optional[str] = None
    flux: Dict[str, Any] | None = None
    pod: Dict[str, Any] | None = None
    containers: List[ContainerConfig] = Field(default_factory=list)

    @field_validator("maxSize")
    @classmethod
    def ensure_max_ge_size(cls, v, values):
        if v is not None and values.get("size") and v < values["size"]:
            raise ValueError("maxSize must be >= size")
        return v

    def to_manifest(self, name: str, namespace: str) -> Dict[str, Any]:
        body = {
            "apiVersion": f"{GROUP}/{VERSION}",
            "kind": "MiniCluster",
            "metadata": {"name": name, "namespace": namespace},
            "spec": json.loads(self.model_dump_json(by_alias=True, exclude_none=True)),
        }
        return body


class FluxOperatorClient:
    """Client for CRUD operations on Flux MiniClusters."""

    def __init__(
        self,
        namespace: str,
        default_minicluster: str,
        allowed_namespaces: Optional[List[str]] = None,
        kubeconfig: Optional[str] = None,
    ) -> None:
        self.default_namespace = namespace
        self.default_minicluster = default_minicluster
        self.allowed_namespaces = [n for n in (allowed_namespaces or []) if n]
        self.kubeconfig = kubeconfig

        self._configure_client()
        self.api = client.CustomObjectsApi()

    def _configure_client(self) -> None:
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except ConfigException:
            try:
                config.load_kube_config(config_file=self.kubeconfig)
                logger.info("Loaded kubeconfig for Flux Operator client")
            except ConfigException as exc:
                raise RuntimeError("Unable to configure Kubernetes client for Flux Operator") from exc

    def _ensure_namespace(self, namespace: Optional[str]) -> str:
        ns = namespace or self.default_namespace
        if self.allowed_namespaces and ns not in self.allowed_namespaces:
            raise PermissionError(f"Namespace '{ns}' is not allowed for MiniCluster operations")
        return ns

    # CRUD operations -----------------------------------------------------
    def list_miniclusters(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        ns = self._ensure_namespace(namespace)
        return self.api.list_namespaced_custom_object(GROUP, VERSION, ns, PLURAL)

    def get_minicluster(self, name: Optional[str] = None, namespace: Optional[str] = None) -> Dict[str, Any]:
        ns = self._ensure_namespace(namespace)
        name = name or self.default_minicluster
        return self.api.get_namespaced_custom_object(GROUP, VERSION, ns, PLURAL, name)

    def apply_minicluster(
        self,
        spec: MiniClusterSpec,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        wait_ready: bool = False,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        ns = self._ensure_namespace(namespace)
        name = name or self.default_minicluster
        body = spec.to_manifest(name=name, namespace=ns)

        existing = self._minicluster_exists(name, ns)
        if existing:
            logger.info("Patching MiniCluster %s/%s", ns, name)
            result = self.api.patch_namespaced_custom_object(GROUP, VERSION, ns, PLURAL, name, body)
        else:
            logger.info("Creating MiniCluster %s/%s", ns, name)
            result = self.api.create_namespaced_custom_object(GROUP, VERSION, ns, PLURAL, body)

        if wait_ready:
            status = self.wait_for_ready(name=name, namespace=ns, timeout=timeout)
            result["status"] = status
        return result

    def scale_minicluster(
        self,
        size: int,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        max_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        ns = self._ensure_namespace(namespace)
        name = name or self.default_minicluster
        patch = {"spec": {"size": size}}
        if max_size is not None:
            patch["spec"]["maxSize"] = max_size
        return self.api.patch_namespaced_custom_object(GROUP, VERSION, ns, PLURAL, name, patch)

    def delete_minicluster(self, name: Optional[str] = None, namespace: Optional[str] = None) -> Dict[str, Any]:
        ns = self._ensure_namespace(namespace)
        name = name or self.default_minicluster
        body = client.V1DeleteOptions(propagation_policy="Foreground")
        return self.api.delete_namespaced_custom_object(
            GROUP,
            VERSION,
            ns,
            PLURAL,
            name,
            body=body,
        )

    # Helpers --------------------------------------------------------------
    def _minicluster_exists(self, name: str, namespace: str) -> bool:
        try:
            self.api.get_namespaced_custom_object(GROUP, VERSION, namespace, PLURAL, name)
            return True
        except client.exceptions.ApiException as exc:  # type: ignore[attr-defined]
            if exc.status == 404:
                return False
            raise

    def wait_for_ready(
        self, name: Optional[str] = None, namespace: Optional[str] = None, timeout: int = 300
    ) -> Dict[str, Any]:
        ns = self._ensure_namespace(namespace)
        name = name or self.default_minicluster
        w = watch.Watch()
        try:
            for event in w.stream(
                self.api.list_namespaced_custom_object,
                GROUP,
                VERSION,
                ns,
                PLURAL,
                timeout_seconds=timeout,
            ):
                obj = event.get("object", {})
                metadata = obj.get("metadata", {})
                if metadata.get("name") != name:
                    continue
                status = obj.get("status", {})
                if self._status_indicates_ready(status):
                    return status
        finally:
            w.stop()
        return {"phase": "Unknown", "reason": "Timeout"}

    @staticmethod
    def _status_indicates_ready(status: Dict[str, Any]) -> bool:
        """Check MiniCluster status for readiness signals across Flux versions."""
        phase = status.get("phase")
        if phase in {"Running", "Succeeded"}:
            return True
        size = status.get("size")
        desired = status.get("maximumSize") or status.get("desiredSize") or status.get("specSize")
        if size and desired and size >= desired:
            return True
        for condition in status.get("conditions", []) or []:
            cond_type = condition.get("type")
            cond_status = condition.get("status")
            if cond_status == "True" and cond_type in {"Running", "Succeeded", "JobMiniClusterReady"}:
                return True
        return False
