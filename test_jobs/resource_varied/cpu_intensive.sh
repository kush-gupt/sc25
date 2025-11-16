#!/bin/bash
#
# cpu_intensive.sh - CPU-intensive computation job
#
# Purpose: Test CPU resource allocation and monitoring
# Expected runtime: ~30 seconds
# Recommended resources: 1 node, 4-8 tasks, 1 CPU per task

echo "=== CPU Intensive Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Available CPUs: $(nproc)"
echo ""

# Function to perform CPU-intensive calculation
cpu_intensive_task() {
    local task_id=$1
    local iterations=5000000

    echo "Task $task_id: Starting CPU-intensive computation..."

    # Calculate prime numbers (CPU intensive)
    local count=0
    for ((n=2; n<$iterations; n++)); do
        if ((n % 100000 == 0)); then
            echo "Task $task_id: Progress - checked $n numbers, found $count primes"
        fi

        # Simple primality test
        local is_prime=1
        for ((i=2; i*i<=n; i++)); do
            if ((n % i == 0)); then
                is_prime=0
                break
            fi
        done

        if ((is_prime == 1)); then
            ((count++))
        fi

        # Only check first 10000 numbers to keep runtime reasonable
        if ((n > 10000)); then
            break
        fi
    done

    echo "Task $task_id: Found $count prime numbers"
    return 0
}

# Get number of parallel tasks to run
NUM_TASKS=${SLURM_NTASKS:-4}
echo "Running $NUM_TASKS parallel CPU-intensive tasks..."
echo ""

# Launch parallel tasks
for i in $(seq 1 $NUM_TASKS); do
    cpu_intensive_task $i &
done

# Wait for all tasks to complete
echo "Waiting for all tasks to complete..."
wait

echo ""
echo "All CPU-intensive tasks completed successfully"
echo "Job completed at: $(date)"
