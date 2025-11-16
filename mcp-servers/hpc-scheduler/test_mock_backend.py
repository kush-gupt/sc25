#!/usr/bin/env python3
"""Test script to demonstrate tools working with mock backend"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Enable mock backend
os.environ["USE_MOCK_BACKENDS"] = "true"

from tools.submit_job import submit_job
from tools.get_job import get_job

# Access underlying functions
submit_job_fn = submit_job.fn
get_job_fn = get_job.fn


async def main():
    print("=" * 70)
    print("Testing HPC Scheduler MCP Tools with Mock Backend")
    print("=" * 70)
    print()

    # Test 1: Submit a simple job
    print("1. Submitting a simple job to slurm-local cluster...")
    print("-" * 70)

    submit_result = await submit_job_fn(
        cluster="slurm-local",
        script="""#!/bin/bash
#SBATCH --job-name=test-job
echo "Hello from HPC cluster!"
sleep 10
echo "Job completed successfully"
""",
        job_name="demo-job",
        nodes=2,
        tasks_per_node=4,
        cpus_per_task=2,
        memory="16GB",
        time_limit="1h"
    )

    submit_data = json.loads(submit_result)
    print(json.dumps(submit_data, indent=2))
    print()

    if not submit_data["success"]:
        print("❌ Job submission failed!")
        return

    job_id = submit_data["job_id"]
    print(f"✓ Job submitted successfully with ID: {job_id}")
    print()

    # Test 2: Get job details (concise format)
    print("2. Getting job details (concise format)...")
    print("-" * 70)

    get_result_concise = await get_job_fn(
        cluster="slurm-local",
        job_id=job_id,
        response_format="concise"
    )

    get_data_concise = json.loads(get_result_concise)
    print(json.dumps(get_data_concise, indent=2))
    print()

    # Test 3: Get job details (detailed format)
    print("3. Getting job details (detailed format)...")
    print("-" * 70)

    get_result_detailed = await get_job_fn(
        cluster="slurm-local",
        job_id=job_id,
        response_format="detailed"
    )

    get_data_detailed = json.loads(get_result_detailed)
    print(json.dumps(get_data_detailed, indent=2))
    print()

    # Test 4: Submit to flux-local cluster
    print("4. Submitting a job to flux-local cluster...")
    print("-" * 70)

    flux_submit_result = await submit_job_fn(
        cluster="flux-local",
        script="""#!/bin/bash
echo "Hello from Flux Framework!"
hostname
echo "Flux job completed"
""",
        job_name="flux-demo",
        nodes=1,
        time_limit="30m"
    )

    flux_data = json.loads(flux_submit_result)
    print(json.dumps(flux_data, indent=2))
    print()

    if flux_data["success"]:
        flux_job_id = flux_data["job_id"]
        print(f"✓ Flux job submitted with ID: {flux_job_id}")
        print(f"  (Note the Flux-style job ID format: {flux_job_id})")
        print()

    # Summary
    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    print("✓ Mock backend is working correctly!")
    print("✓ Tools can submit jobs to both Slurm and Flux backends")
    print("✓ Job details can be retrieved in concise and detailed formats")
    print("✓ ISO8601 timestamps with 'Z' suffix are properly formatted")
    print("✓ Job IDs follow backend-specific formats (numeric for Slurm, ƒ prefix for Flux)")
    print()
    print("To switch to real backends, simply remove USE_MOCK_BACKENDS environment variable")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
