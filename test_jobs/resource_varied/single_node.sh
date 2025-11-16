#!/bin/bash
#
# single_node.sh - Single-node computation job
#
# Purpose: Test basic single-node resource allocation
# Expected runtime: ~10 seconds
# Recommended resources: 1 node, 4 tasks, 2 CPUs per task

echo "=== Single Node Computation Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Number of CPUs available: $(nproc)"
echo ""

# Simulate some computational work
echo "Performing single-node computation..."
echo "Running 4 parallel tasks..."

for i in {1..4}; do
    {
        echo "  Task $i: Starting on CPU core..."
        # Simulate CPU work
        result=$(seq 1 1000000 | awk '{sum+=$1} END {print sum}')
        echo "  Task $i: Completed (result: $result)"
    } &
done

# Wait for all background tasks to complete
wait

echo ""
echo "All tasks completed successfully"
echo "Job completed at: $(date)"
