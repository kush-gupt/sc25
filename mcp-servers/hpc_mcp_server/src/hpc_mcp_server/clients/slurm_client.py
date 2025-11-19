"""Slurm REST API client reused by the unified MCP server."""
from __future__ import annotations

import os
import subprocess
from typing import Dict, Optional

import requests


class SlurmClient:
    """Client for interacting with Slurm REST API (slurmrestd)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        api_version: str = "v0.0.43",
        namespace: str | None = None,
        controller_pod: str = "slurm-controller-0",
    ) -> None:
        self.base_url = base_url or os.getenv(
            "SLURM_REST_URL", "http://slurm-restapi.slurm.svc.cluster.local:6820"
        )
        self.api_version = api_version
        self.namespace = namespace or os.getenv("SLURM_NAMESPACE", "slurm")
        self.controller_pod = controller_pod
        self.user = os.getenv("SLURM_USER", "slurm")
        self.token = token or os.getenv("SLURM_JWT", "") or self._generate_token()

        self.headers = {
            "Content-Type": "application/json",
            "X-SLURM-USER-NAME": self.user,
        }
        if self.token:
            self.headers["X-SLURM-USER-TOKEN"] = self.token

    def _generate_token(self) -> str:
        try:
            try:
                from kubernetes import client, config
                from kubernetes.stream import stream

                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()

                v1 = client.CoreV1Api()
                resp = stream(
                    v1.connect_get_namespaced_pod_exec,
                    self.controller_pod,
                    self.namespace,
                    container="slurmctld",
                    command=["scontrol", "token", "lifespan=86400"],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=False,
                )
                resp.run_forever(timeout=10)
                output = resp.read_stdout()
                for line in output.split("\n"):
                    if line.startswith("SLURM_JWT="):
                        return line.split("=", 1)[1].strip()
            except ImportError:
                result = subprocess.run(
                    [
                        "kubectl",
                        "exec",
                        "-n",
                        self.namespace,
                        self.controller_pod,
                        "-c",
                        "slurmctld",
                        "--",
                        "scontrol",
                        "token",
                        "lifespan=86400",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if line.startswith("SLURM_JWT="):
                            return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return ""

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/slurm/{self.api_version}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as exc:
            return {
                "error": f"Cannot connect to slurm-restapi at {self.base_url}.",
                "success": False,
                "details": str(exc),
            }
        except requests.exceptions.RequestException as exc:
            return {"error": str(exc), "success": False}

    def ping(self) -> Dict:
        return self._make_request("GET", "ping")

    def submit_job(
        self,
        script: str,
        job_name: Optional[str] = None,
        account: Optional[str] = None,
        partition: Optional[str] = None,
        nodes: Optional[int] = None,
        tasks: Optional[int] = None,
        memory: Optional[str] = None,
        time_limit: Optional[int] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        working_dir = working_dir or "/tmp"
        env = env or {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        }

        job_data = {
            "job": {
                "script": script,
                "current_working_directory": working_dir,
                "environment": [f"{k}={v}" for k, v in env.items()],
            }
        }

        if job_name:
            job_data["job"]["name"] = job_name
        if account:
            job_data["job"]["account"] = account
        if partition:
            job_data["job"]["partition"] = partition
        if nodes:
            job_data["job"]["nodes"] = nodes
        if tasks:
            job_data["job"]["tasks"] = tasks
        if memory:
            job_data["job"]["memory_per_cpu"] = memory
        if time_limit:
            job_data["job"]["time_limit"] = time_limit
        if output:
            job_data["job"]["standard_output"] = output
        if error:
            job_data["job"]["standard_error"] = error

        return self._make_request("POST", "job/submit", job_data)

    def get_job(self, job_id: str) -> Dict:
        return self._make_request("GET", f"job/{job_id}")

    def list_jobs(self) -> Dict:
        return self._make_request("GET", "jobs")

    def cancel_job(self, job_id: str) -> Dict:
        return self._make_request("DELETE", f"job/{job_id}")

    def get_nodes(self) -> Dict:
        return self._make_request("GET", "nodes")

    def get_partitions(self) -> Dict:
        return self._make_request("GET", "partitions")
