"""Flux Client - Interacts with Flux via Kubernetes exec API."""
import os
import json
from typing import Dict, List, Optional, Any
from kubernetes import client, config
from kubernetes.stream import stream


class FluxClient:
    """Client for interacting with Flux Framework via Kubernetes API"""
    
    def __init__(self, flux_uri: Optional[str] = None, namespace: Optional[str] = None,
                 minicluster: Optional[str] = None):
        """
        Initialize Flux client.
        
        Args:
            flux_uri: Flux URI for connection (default: from FLUX_URI env)
            namespace: Kubernetes namespace (default: from FLUX_NAMESPACE env)
            minicluster: MiniCluster name (default: from FLUX_MINICLUSTER env)
        """
        self.flux_uri = flux_uri or os.getenv("FLUX_URI", "local:///mnt/flux/view/run/flux/local")
        self.namespace = namespace or os.getenv("FLUX_NAMESPACE", "flux-operator")
        self.minicluster = minicluster or os.getenv("FLUX_MINICLUSTER", "flux-sample")
        self.pod_name = None
        
        # Initialize Kubernetes client (in-cluster config)
        try:
            config.load_incluster_config()
        except config.ConfigException:
            # Fall back to kubeconfig for local development
            try:
                config.load_kube_config()
            except config.ConfigException:
                pass
        
        self.v1 = client.CoreV1Api()
    
    def _get_flux_pod(self) -> Optional[str]:
        """Get the first Flux pod from the MiniCluster"""
        if self.pod_name:
            return self.pod_name
        
        try:
            pods = self.v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"job-name={self.minicluster}"
            )
            
            if pods.items:
                self.pod_name = pods.items[0].metadata.name
                return self.pod_name
        except Exception:
            pass
        
        return None
    
    def _run_flux_cmd(self, args: List[str]) -> Dict:
        """Run flux CLI command via Kubernetes exec API"""
        pod = self._get_flux_pod()
        if not pod:
            return {"error": "No Flux pod found", "success": False}
        
        command = ["bash", "-c", f"FLUX_URI={self.flux_uri} flux {' '.join(args)}"]
        
        try:
            resp = stream(
                self.v1.connect_get_namespaced_pod_exec,
                pod,
                self.namespace,
                container=self.minicluster,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False
            )
            
            resp.run_forever(timeout=30)
            
            stdout = ""
            stderr = ""
            
            if resp.peek_stdout():
                stdout = resp.read_stdout()
            if resp.peek_stderr():
                stderr = resp.read_stderr()
            
            return_code = resp.returncode if hasattr(resp, 'returncode') else 0
            
            if stderr and not stdout:
                return {
                    "output": stdout,
                    "error": stderr,
                    "success": False,
                    "return_code": return_code
                }
            
            return {
                "output": stdout,
                "error": stderr if stderr else None,
                "success": True,
                "return_code": return_code
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def submit_job(self, command: str, script: Optional[str] = None,
                   nodes: Optional[int] = None, tasks: Optional[int] = None,
                   cores_per_task: Optional[int] = None,
                   time_limit: Optional[str] = None,
                   job_name: Optional[str] = None,
                   output: Optional[str] = None,
                   env: Optional[Dict[str, str]] = None) -> Dict:
        """
        Submit a job to Flux.
        
        Args:
            command: Command to run
            script: Path to script file (if submitting script)
            nodes: Number of nodes
            tasks: Number of tasks
            cores_per_task: Cores per task
            time_limit: Time limit (e.g., "1h", "30m")
            job_name: Name for the job
            output: Output file path
            env: Environment variables
            
        Returns:
            Dictionary with job submission response including job ID
        """
        args = ["submit"]
        
        if nodes:
            args.extend(["-N", str(nodes)])
        if tasks:
            args.extend(["-n", str(tasks)])
        if cores_per_task:
            args.extend(["-c", str(cores_per_task)])
        if time_limit:
            args.extend(["-t", time_limit])
        if job_name:
            args.extend(["--job-name", job_name])
        if output:
            args.extend(["-o", output])
        
        if script:
            args.append(script)
        else:
            # Escape command for bash
            args.append(f'"{command}"')
        
        result = self._run_flux_cmd(args)
        if result.get("success"):
            # Extract job ID from output (format: "ƒXXXXXXX")
            output = result.get("output", "")
            import re
            match = re.search(r'ƒ([A-Za-z0-9]+)', output)
            if match:
                result["jobid"] = f"ƒ{match.group(1)}"
        
        return result
    
    def submit_with_dependencies(self, command: str, dependency_type: str,
                                dependency_jobid: str, **kwargs) -> Dict:
        """
        Submit job with dependencies.
        
        Args:
            command: Command to run
            dependency_type: Type of dependency (afterok, afterany, etc.)
            dependency_jobid: Job ID to depend on
            **kwargs: Additional job parameters
            
        Returns:
            Dictionary with job submission response
        """
        args = ["submit", f"--dependency={dependency_type}:{dependency_jobid}"]
        
        if kwargs.get("job_name"):
            args.extend(["--job-name", kwargs["job_name"]])
        if kwargs.get("nodes"):
            args.extend(["-N", str(kwargs["nodes"])])
        if kwargs.get("tasks"):
            args.extend(["-n", str(kwargs["tasks"])])
        
        args.append(f'"{command}"')
        
        result = self._run_flux_cmd(args)
        if result.get("success"):
            output = result.get("output", "")
            import re
            match = re.search(r'ƒ([A-Za-z0-9]+)', output)
            if match:
                result["jobid"] = f"ƒ{match.group(1)}"
        
        return result
    
    def get_job(self, jobid: str) -> Dict:
        """
        Get detailed information about a specific job.
        
        Args:
            jobid: Job ID to query
            
        Returns:
            Dictionary with job information
        """
        result = self._run_flux_cmd(["jobs", "-a", "-no", "all", jobid])
        return result
    
    def list_jobs(self, state: Optional[str] = None, user: Optional[str] = None) -> Dict:
        """
        List jobs.
        
        Args:
            state: Filter by state (active, inactive, running, etc.)
            user: Filter by user
            
        Returns:
            Dictionary with list of jobs
        """
        args = ["jobs", "-a"]
        
        if state:
            args.extend(["--filter", state])
        
        result = self._run_flux_cmd(args)
        return result
    
    def cancel_job(self, jobid: str) -> Dict:
        """
        Cancel a job.
        
        Args:
            jobid: Job ID to cancel
            
        Returns:
            Dictionary with cancellation response
        """
        result = self._run_flux_cmd(["cancel", jobid])
        if result.get("success"):
            return {
                "success": True,
                "jobid": jobid,
                "message": f"Job {jobid} cancelled"
            }
        return result
    
    def get_resources(self) -> Dict:
        """
        Get information about available resources.
        
        Returns:
            Dictionary with resource information
        """
        result = self._run_flux_cmd(["resource", "list"])
        return result
    
    def get_job_output(self, jobid: str) -> Dict:
        """
        Get output from a completed job.
        
        Args:
            jobid: Job ID
            
        Returns:
            Dictionary with job output
        """
        result = self._run_flux_cmd(["job", "attach", jobid])
        return result
    
    def get_job_stats(self, jobid: str) -> Dict:
        """
        Get performance statistics for a job.
        
        Args:
            jobid: Job ID
            
        Returns:
            Dictionary with job statistics (runtime, wait time, etc.)
        """
        # Get job details with specific format
        result = self._run_flux_cmd([
            "jobs", "-a", "-no",
            "{id},{name},{runtime},{t_submit},{t_run},{t_cleanup},{t_inactive},{result}",
            jobid
        ])
        
        if result.get("success"):
            output = result.get("output", "").strip()
            if output:
                parts = output.split(",")
                if len(parts) >= 8:
                    return {
                        "success": True,
                        "jobid": parts[0],
                        "name": parts[1],
                        "runtime": float(parts[2]) if parts[2] else 0,
                        "t_submit": float(parts[3]) if parts[3] else 0,
                        "t_run": float(parts[4]) if parts[4] else 0,
                        "t_cleanup": float(parts[5]) if parts[5] else 0,
                        "t_inactive": float(parts[6]) if parts[6] else 0,
                        "result": parts[7],
                        "wait_time": (float(parts[4]) - float(parts[3])) if parts[3] and parts[4] else 0
                    }
        
        return result
    
    def bulk_submit(self, commands: List[str], **kwargs) -> Dict:
        """
        Submit multiple jobs.
        
        Args:
            commands: List of commands to submit
            **kwargs: Job parameters to apply to all jobs
            
        Returns:
            Dictionary with list of submitted job IDs
        """
        job_ids = []
        errors = []
        
        for cmd in commands:
            result = self.submit_job(cmd, **kwargs)
            if result.get("success"):
                job_ids.append(result.get("jobid"))
            else:
                errors.append({"command": cmd, "error": result.get("error")})
        
        return {
            "success": len(errors) == 0,
            "job_ids": job_ids,
            "errors": errors if errors else None,
            "submitted": len(job_ids),
            "failed": len(errors)
        }
    
    def get_queue_status(self) -> Dict:
        """
        Get current queue status.
        
        Returns:
            Dictionary with queue statistics
        """
        result = self._run_flux_cmd(["jobs", "-a"])
        
        if result.get("success"):
            output = result.get("output", "")
            lines = output.strip().split("\n")
            
            # Count jobs by state
            running = pending = complete = 0
            for line in lines[1:]:  # Skip header
                if "RUNNING" in line or "RUN" in line:
                    running += 1
                elif "PENDING" in line or "DEPEND" in line:
                    pending += 1
                elif "INACTIVE" in line or "COMPLETED" in line:
                    complete += 1
            
            return {
                "success": True,
                "running": running,
                "pending": pending,
                "completed": complete,
                "total": len(lines) - 1
            }
        
        return result
