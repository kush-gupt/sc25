#!/bin/bash
#
# multi_node.sh - Multi-node MPI-style job
#
# Purpose: Test multi-node resource allocation
# Expected runtime: ~15 seconds
# Recommended resources: 2-4 nodes, 4 tasks per node
#
# Note: This simulates MPI-style parallel work without requiring actual MPI

echo "=== Multi-Node Parallel Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

# Check if we're running in Slurm environment
if [ -n "$SLURM_JOB_ID" ]; then
    echo "Slurm Job ID: $SLURM_JOB_ID"
    echo "Slurm Nodes: $SLURM_JOB_NUM_NODES"
    echo "Slurm Tasks: $SLURM_NTASKS"
    echo "Slurm Task ID: $SLURM_PROCID"
    TOTAL_TASKS=${SLURM_NTASKS:-4}
    TASK_ID=${SLURM_PROCID:-0}
elif [ -n "$FLUX_JOB_ID" ]; then
    echo "Flux Job ID: $FLUX_JOB_ID"
    TOTAL_TASKS=${FLUX_TASK_COUNT:-4}
    TASK_ID=${FLUX_TASK_RANK:-0}
else
    echo "Not running under a scheduler (testing mode)"
    TOTAL_TASKS=4
    TASK_ID=0
fi

echo ""
echo "=== Parallel Task Configuration ==="
echo "Total tasks: $TOTAL_TASKS"
echo "This task ID: $TASK_ID"
echo ""

# Simulate distributed computation
echo "Performing distributed computation..."
CHUNK_SIZE=$((1000000 / TOTAL_TASKS))
START=$((TASK_ID * CHUNK_SIZE + 1))
END=$(((TASK_ID + 1) * CHUNK_SIZE))

echo "Task $TASK_ID processing range: $START to $END"
result=$(seq $START $END | awk '{sum+=$1} END {print sum}')
echo "Task $TASK_ID result: $result"

echo ""
echo "Task $TASK_ID completed at: $(date)"
