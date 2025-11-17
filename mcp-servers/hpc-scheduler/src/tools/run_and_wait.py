"""Submit a job, wait for completion, and return output (blocking operation)"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": False,  # This submits a job, not read-only
        "idempotentHint": False,  # Multiple calls create multiple jobs
        "openWorldHint": False,
    }
)
async def run_and_wait(
    cluster: Annotated[str, Field(description="Cluster name")],
    script: Annotated[str, Field(description="Job script content")],
    job_name: Annotated[str | None, Field(description="Name for the job")] = None,
    nodes: Annotated[int | None, Field(description="Number of nodes")] = None,
    tasks_per_node: Annotated[int | None, Field(description="Tasks per node")] = None,
    time_limit: Annotated[str | None, Field(description="Time limit. Flux: use '10m', '1h', '30s'. Slurm: use '10m', '1h', or '1:30:00'")] = None,
    timeout_minutes: Annotated[int, Field(description="Maximum time to wait")] = 60,
    poll_interval: Annotated[int, Field(description="Seconds between status checks")] = 10,
) -> str:
    """Submit a job, wait for completion, and return output (blocking operation)

    This tool submits a job and polls until completion or timeout, returning the
    job output directly. Reduces multi-step agent interactions for short-running jobs.

    Args:
        cluster: Cluster name
        script: Job script content
        job_name: Name for the job
        nodes: Number of nodes
        tasks_per_node: Tasks per node
        time_limit: Time limit
        timeout_minutes: Maximum time to wait (default: 60)
        poll_interval: Seconds between status checks (default: 10)

    Returns:
        JSON string containing:
        - success: bool indicating if job completed successfully
        - job_id: string job ID
        - state: string job state (COMPLETED|FAILED|TIMEOUT)
        - exit_code: integer exit code (if available)
        - runtime: string runtime duration (HH:MM:SS)
        - stdout: string stdout content
        - stderr: string stderr content
        - error: string error message (if failed or timeout)

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    # Validate inputs
    if not cluster or not cluster.strip():
        raise ToolError("Cluster name cannot be empty")

    if not script or not script.strip():
        raise ToolError("Script cannot be empty")

    if timeout_minutes < 1:
        raise ToolError(f"timeout_minutes must be >= 1, got {timeout_minutes}")

    if poll_interval < 1:
        raise ToolError(f"poll_interval must be >= 1, got {poll_interval}")

    # Import tool functions
    from tools.submit_job import submit_job
    from tools.get_job import get_job
    from tools.get_job_output import get_job_output

    # Access underlying functions
    submit_job_fn = submit_job.fn
    get_job_fn = get_job.fn
    get_job_output_fn = get_job_output.fn

    try:
        # Step 1: Submit the job
        submit_result_str = await submit_job_fn(
            cluster=cluster,
            script=script,
            job_name=job_name,
            nodes=nodes,
            tasks_per_node=tasks_per_node,
            time_limit=time_limit,
        )

        submit_result = json.loads(submit_result_str)

        if not submit_result.get("success"):
            return json.dumps({
                "success": False,
                "error": f"Job submission failed: {submit_result.get('error', 'Unknown error')}",
            }, indent=2)

        job_id = submit_result.get("job_id")
        if not job_id:
            return json.dumps({
                "success": False,
                "error": "Job submission succeeded but no job_id returned",
            }, indent=2)

        # Step 2: Poll for completion
        start_time = datetime.now()
        timeout_time = start_time + timedelta(minutes=timeout_minutes)

        final_state = None
        final_exit_code = None
        final_runtime = None

        # Terminal states that indicate job is done
        terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "PREEMPTED"}

        while datetime.now() < timeout_time:
            # Get job status
            job_status_str = await get_job_fn(
                cluster=cluster,
                job_id=job_id,
                response_format="concise",
            )

            job_status = json.loads(job_status_str)

            if not job_status.get("success"):
                # If we can't get job status, it might have already completed
                # Try to get output anyway
                break

            job_info = job_status.get("job", {})
            current_state = job_info.get("state")

            # Check if job reached terminal state
            if current_state in terminal_states:
                final_state = current_state
                final_exit_code = job_info.get("exit_code")
                final_runtime = job_info.get("runtime")
                break

            # Wait before polling again
            await asyncio.sleep(poll_interval)

        # Step 3: Determine final state
        if final_state is None:
            # Timeout occurred
            final_state = "TIMEOUT"
            error_message = f"Job did not complete within {timeout_minutes} minutes. Job continues running."
        else:
            error_message = None if final_state == "COMPLETED" else f"Job ended with state: {final_state}"

        # Step 4: Get job output
        stdout_content = ""
        stderr_content = ""

        try:
            output_result_str = await get_job_output_fn(
                cluster=cluster,
                job_id=job_id,
                output_type="both",
            )

            output_result = json.loads(output_result_str)

            if output_result.get("success"):
                stdout_content = output_result.get("stdout", "")
                stderr_content = output_result.get("stderr", "")
        except Exception as output_error:
            # If we can't get output, include that in the error
            if error_message:
                error_message += f" | Could not retrieve output: {str(output_error)}"
            else:
                error_message = f"Could not retrieve output: {str(output_error)}"

        # Step 5: Build final response
        result = {
            "success": final_state == "COMPLETED",
            "job_id": job_id,
            "state": final_state,
            "exit_code": final_exit_code,
            "runtime": final_runtime or "unknown",
            "stdout": stdout_content,
            "stderr": stderr_content,
        }

        if error_message:
            result["error"] = error_message

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"run_and_wait failed: {str(e)}",
        }, indent=2)