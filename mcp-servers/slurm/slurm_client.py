"""Slurm REST API Client - Interacts with slurmrestd in Kubernetes."""
import os
import requests
import json
import subprocess
from typing import Dict, List, Optional, Any


class SlurmClient:
    """Client for interacting with Slurm REST API (slurmrestd)"""
    
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, 
                 api_version: str = "v0.0.43"):
        """
        Initialize Slurm REST API client.
        
        Args:
            base_url: Base URL for slurm-restapi (default: http://slurm-restapi.slurm.svc.cluster.local:6820)
            token: JWT authentication token (optional, will use X-SLURM-USER-NAME for now)
            api_version: API version to use
        """
        self.base_url = base_url or os.getenv("SLURM_REST_URL", "http://slurm-restapi.slurm.svc.cluster.local:6820")
        self.api_version = api_version
        self.namespace = os.getenv("SLURM_NAMESPACE", "slurm")
        self.controller_pod = "slurm-controller-0"
        self.user = os.getenv("SLURM_USER", "slurm")
        
        # Try to get token from parameter, env, or generate new one
        self.token = token or os.getenv("SLURM_JWT", "") or self._generate_token()
        
        self.headers = {
            "Content-Type": "application/json",
            "X-SLURM-USER-NAME": self.user,
        }
        if self.token:
            self.headers["X-SLURM-USER-TOKEN"] = self.token
    
    def _generate_token(self) -> str:
        """Generate JWT token from Slurm controller with 24-hour lifespan"""
        try:
            # Try using Kubernetes Python client first (if available)
            try:
                from kubernetes import client, config
                from kubernetes.stream import stream
                
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config()
                
                v1 = client.CoreV1Api()
                resp = stream(
                    v1.connect_get_namespaced_pod_exec,
                    self.controller_pod,
                    self.namespace,
                    container='slurmctld',
                    command=['scontrol', 'token', 'lifespan=86400'],  # 24 hours
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=False
                )
                resp.run_forever(timeout=10)
                output = resp.read_stdout()
                
                # Parse SLURM_JWT=token
                for line in output.split('\n'):
                    if line.startswith('SLURM_JWT='):
                        return line.split('=', 1)[1].strip()
            except ImportError:
                # Fall back to kubectl if Kubernetes client not available
                result = subprocess.run(
                    ['kubectl', 'exec', '-n', self.namespace,
                     self.controller_pod, '-c', 'slurmctld', '--',
                     'scontrol', 'token', 'lifespan=86400'],  # 24 hours
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('SLURM_JWT='):
                            return line.split('=', 1)[1].strip()
        except Exception as e:
            # If token generation fails, continue without token
            # (some APIs might work with just user header)
            pass
        
        return ""
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Slurm REST API"""
        url = f"{self.base_url}/slurm/{self.api_version}/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            return {
                "error": f"Cannot connect to slurm-restapi at {self.base_url}. Make sure slurm-restapi service is running.",
                "success": False,
                "details": str(e)
            }
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "success": False}
    
    def ping(self) -> Dict:
        """Test connectivity to slurm-restapi"""
        return self._make_request("GET", "ping")
    
    def submit_job(self, script: str, job_name: Optional[str] = None,
                   account: Optional[str] = None, partition: Optional[str] = None,
                   nodes: Optional[int] = None, tasks: Optional[int] = None,
                   memory: Optional[str] = None, time_limit: Optional[int] = None,
                   output: Optional[str] = None, error: Optional[str] = None,
                   env: Optional[Dict[str, str]] = None,
                   working_dir: Optional[str] = None, **kwargs) -> Dict:
        """
        Submit a batch job to Slurm.
        
        Args:
            script: Job script content
            job_name: Name for the job
            account: Account to charge
            partition: Partition to submit to
            nodes: Number of nodes
            tasks: Number of tasks
            memory: Memory requirement (e.g., "1G")
            time_limit: Time limit in minutes
            output: Path for stdout
            error: Path for stderr
            env: Environment variables
            working_dir: Working directory (defaults to /tmp if not provided)
            
        Returns:
            Dictionary with job submission response
        """
        # Set default working directory if not provided (required by Slurm)
        if not working_dir:
            working_dir = "/tmp"
        
        # Set default environment with PATH if not provided
        # Based on SlinkyProject/slurm-client best practices
        if not env:
            env = {
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            }
        
        job_data = {
            "job": {
                "script": script,
                "current_working_directory": working_dir,
                "environment": [f"{k}={v}" for k, v in env.items()]
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
    
    def submit_array_job(self, script: str, array_spec: str, **kwargs) -> Dict:
        """
        Submit an array job to Slurm.
        
        Args:
            script: Job script content
            array_spec: Array specification (e.g., "1-10", "1-10:2")
            **kwargs: Additional job parameters (same as submit_job)
            
        Returns:
            Dictionary with job submission response
        """
        # Prepend array directive to script
        if not script.startswith("#!/bin/bash"):
            script = "#!/bin/bash\n" + script
        
        lines = script.split('\n')
        # Insert array directive after shebang
        lines.insert(1, f"#SBATCH --array={array_spec}")
        script_with_array = '\n'.join(lines)
        
        return self.submit_job(script_with_array, **kwargs)
    
    def get_job(self, job_id: str) -> Dict:
        """
        Get detailed information about a specific job.
        
        Args:
            job_id: Job ID to query
            
        Returns:
            Dictionary with job information
        """
        return self._make_request("GET", f"job/{job_id}")
    
    def list_jobs(self, user: Optional[str] = None, state: Optional[str] = None) -> Dict:
        """
        List jobs in the system.
        
        Args:
            user: Filter by username
            state: Filter by job state (PENDING, RUNNING, COMPLETED, etc.)
            
        Returns:
            Dictionary with list of jobs
        """
        return self._make_request("GET", "jobs")
    
    def cancel_job(self, job_id: str, signal: Optional[str] = None) -> Dict:
        """
        Cancel a job.
        
        Args:
            job_id: Job ID to cancel
            signal: Signal to send (default: SIGTERM)
            
        Returns:
            Dictionary with cancellation response
        """
        return self._make_request("DELETE", f"job/{job_id}")
    
    def get_nodes(self) -> Dict:
        """
        Get information about compute nodes.
        
        Returns:
            Dictionary with node information
        """
        return self._make_request("GET", "nodes")
    
    def get_node(self, node_name: str) -> Dict:
        """
        Get detailed information about a specific node.
        
        Args:
            node_name: Name of the node
            
        Returns:
            Dictionary with node information
        """
        return self._make_request("GET", f"node/{node_name}")
    
    def get_partitions(self) -> Dict:
        """
        Get information about partitions.
        
        Returns:
            Dictionary with partition information
        """
        return self._make_request("GET", "partitions")
    
    def get_partition(self, partition_name: str) -> Dict:
        """
        Get detailed information about a specific partition.
        
        Args:
            partition_name: Name of the partition
            
        Returns:
            Dictionary with partition information
        """
        return self._make_request("GET", f"partition/{partition_name}")
    
    def get_accounting(self, job_id: Optional[str] = None, 
                      start_time: Optional[str] = None,
                      end_time: Optional[str] = None) -> Dict:
        """
        Get accounting information for jobs.
        Note: This requires slurmdbd to be configured.
        
        Args:
            job_id: Specific job ID to query
            start_time: Start time for query
            end_time: End time for query
            
        Returns:
            Dictionary with accounting information
        """
        # The accounting endpoint may vary based on API version
        endpoint = "jobs"
        if job_id:
            endpoint = f"job/{job_id}"
        return self._make_request("GET", endpoint)
    
    def get_diag(self) -> Dict:
        """
        Get diagnostic information about the Slurm cluster.
        
        Returns:
            Dictionary with diagnostic information
        """
        return self._make_request("GET", "diag")
    
    def get_job_output(self, job_id: str, output_path: Optional[str] = None) -> Dict:
        """
        Retrieve job output file contents via Kubernetes Python API.
        
        Args:
            job_id: Job ID to retrieve output for
            output_path: Specific output file path (optional, will try to detect from job info)
            
        Returns:
            Dictionary with output contents or error message
        """
        try:
            # Get job info to find output file path and node
            job_info = self.get_job(job_id)
            
            if "jobs" not in job_info or len(job_info["jobs"]) == 0:
                return {"error": f"Job {job_id} not found", "success": False}
            
            job = job_info["jobs"][0]
            
            # Determine output file path
            if not output_path:
                output_path = job.get("standard_output") or f"/tmp/slurm-{job_id}.out"
            
            # Expand Slurm placeholders
            output_path = output_path.replace("%j", str(job_id))
            output_path = output_path.replace("%J", str(job_id))
            
            # Get the node where job ran
            nodes = job.get("nodes", "")
            if not nodes:
                return {"error": "Cannot determine job execution node", "success": False}
            
            # Get first node if multiple
            node = nodes.split(",")[0] if "," in nodes else nodes
            
            # Try to read file using Kubernetes API
            try:
                from kubernetes import client, config
                from kubernetes.stream import stream
                
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config()
                
                v1 = client.CoreV1Api()
                
                # Find worker pod
                pods = v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector='app.kubernetes.io/component=worker'
                )
                
                if not pods.items:
                    return {
                        "error": "No worker pods found",
                        "success": False,
                        "job_id": job_id
                    }
                
                pod_name = pods.items[0].metadata.name
                
                # Read file from pod
                exec_command = ['cat', output_path]
                resp = stream(
                    v1.connect_get_namespaced_pod_exec,
                    pod_name,
                    self.namespace,
                    container='slurmd',
                    command=exec_command,
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=False
                )
                resp.run_forever(timeout=30)
                
                output = resp.read_stdout()
                error = resp.read_stderr()
                
                if error:
                    return {
                        "error": f"Failed to read file: {error}",
                        "success": False,
                        "job_id": job_id,
                        "output_path": output_path
                    }
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "output_path": output_path,
                    "node": node,
                    "pod": pod_name,
                    "contents": output
                }
                
            except ImportError:
                return {
                    "error": "Kubernetes Python client not available",
                    "success": False,
                    "job_id": job_id,
                    "suggestion": "Use the helper script: ./scripts/get_job_results.sh"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to retrieve job output: {str(e)}",
                "success": False,
                "job_id": job_id
            }
