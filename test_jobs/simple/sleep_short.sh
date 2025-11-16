#!/bin/bash
#
# sleep_short.sh - Short-duration sleep job
#
# Purpose: Test job polling and status monitoring
# Expected runtime: 30 seconds
# Resources: Minimal (1 node, 1 task)

echo "=== Sleep Test Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

SLEEP_DURATION=30
echo "Starting sleep for ${SLEEP_DURATION} seconds..."

for i in {1..6}; do
    echo "Progress: $((i * 5)) seconds elapsed..."
    sleep 5
done

echo ""
echo "Sleep completed successfully!"
echo "Job completed at: $(date)"
