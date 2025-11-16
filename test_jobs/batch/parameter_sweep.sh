#!/bin/bash
#
# parameter_sweep.sh - Parameter sweep using array jobs
#
# Purpose: Test batch job submission with array task IDs
# Expected runtime: ~10 seconds per task
# Recommended submission:
#   Slurm: --array=1-10 or --array=0-9
#   Flux: Use submit_batch with commands list
#
# This script uses the $SLURM_ARRAY_TASK_ID variable to process
# different parameters in parallel

echo "=== Parameter Sweep Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

# Get the array task ID (Slurm) or use a default for testing
if [ -n "$SLURM_ARRAY_TASK_ID" ]; then
    TASK_ID=$SLURM_ARRAY_TASK_ID
    echo "Slurm Array Task ID: $TASK_ID"
elif [ -n "$FLUX_TASK_RANK" ]; then
    TASK_ID=$FLUX_TASK_RANK
    echo "Flux Task Rank: $TASK_ID"
else
    TASK_ID=${1:-1}  # Use command line arg or default to 1
    echo "Running in test mode with Task ID: $TASK_ID"
fi

echo ""

# Define parameter values to sweep
# In a real scenario, these might be learning rates, batch sizes, etc.
PARAMETERS=(
    "0.001"
    "0.005"
    "0.01"
    "0.05"
    "0.1"
    "0.5"
    "1.0"
    "5.0"
    "10.0"
    "50.0"
)

# Get the parameter for this task
# Array indexing starts at 0, but SLURM_ARRAY_TASK_ID often starts at 1
PARAM_INDEX=$((TASK_ID - 1))
if [ $PARAM_INDEX -lt 0 ]; then
    PARAM_INDEX=0
fi

if [ $PARAM_INDEX -ge ${#PARAMETERS[@]} ]; then
    echo "ERROR: Task ID $TASK_ID exceeds parameter array size"
    exit 1
fi

PARAM=${PARAMETERS[$PARAM_INDEX]}

echo "=== Task Configuration ==="
echo "Task ID: $TASK_ID"
echo "Parameter value: $PARAM"
echo ""

# Simulate parameter sweep computation
echo "Running experiment with parameter=$PARAM..."
echo "Initializing..."
sleep 2

# Simulate some computation
echo "Processing data..."
RESULT=$(echo "scale=4; $PARAM * 100 + $TASK_ID" | bc 2>/dev/null || echo "$TASK_ID")
sleep 3

echo "Finalizing results..."
sleep 1

echo ""
echo "=== Results ==="
echo "Task ID: $TASK_ID"
echo "Parameter: $PARAM"
echo "Result: $RESULT"
echo "Status: SUCCESS"

# In a real scenario, you might save results to a file
OUTPUT_FILE="/tmp/result_task_${TASK_ID}.txt"
echo "Saving results to $OUTPUT_FILE"
cat > $OUTPUT_FILE << EOF
Task ID: $TASK_ID
Parameter: $PARAM
Result: $RESULT
Completed: $(date)
EOF

echo ""
echo "Job completed at: $(date)"

exit 0
