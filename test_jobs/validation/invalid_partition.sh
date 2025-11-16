#!/bin/bash
#
# invalid_partition.sh - References non-existent partition
#
# Purpose: Test validation of partition/queue names (Slurm-specific)
# Expected validation: ERROR - partition does not exist
# Recommended submission parameters:
#   --partition=nonexistent-partition-12345
#
# Note: This script itself is valid, but submitting to a
# non-existent partition should be caught by validate_script

echo "=== Invalid Partition Test ==="
echo "This job is configured to run on a non-existent partition"
echo "The validate_script tool should detect this issue"
echo ""
echo "Target partition: nonexistent-partition-12345"
echo ""
echo "If you see this output, validation was bypassed!"
echo ""
echo "Running on node: $(hostname)"
echo "Job started at: $(date)"

# The actual work is trivial
echo "Hello from invalid partition test"
sleep 5

echo "Job completed at: $(date)"
