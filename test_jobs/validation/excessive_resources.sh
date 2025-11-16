#!/bin/bash
#
# excessive_resources.sh - Requests more resources than available
#
# Purpose: Test validation of resource limits
# Expected validation: ERROR/WARNING - resource limits exceeded
# Recommended submission parameters:
#   --nodes=1000 (intentionally excessive)
#   --time-limit=999:00:00 (intentionally excessive)
#   --memory=9999GB (intentionally excessive)
#
# Note: This script itself is valid, but the resource requests
# should be caught by validate_script when paired with the parameters above

echo "=== Excessive Resource Request Test ==="
echo "This job script requests impossible resource allocations"
echo "The validate_script tool should catch these issues before submission"
echo ""
echo "Requested resources:"
echo "  - Nodes: 1000 (likely exceeds cluster capacity)"
echo "  - Memory: 9999GB per node (likely exceeds node capacity)"
echo "  - Time limit: 999 hours (likely exceeds partition limits)"
echo ""
echo "If you see this output, validation was bypassed!"
echo ""
echo "Running on node: $(hostname)"
echo "Job started at: $(date)"

# The actual work is trivial
echo "Hello World"
sleep 5

echo "Job completed at: $(date)"
