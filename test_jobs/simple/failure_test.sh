#!/bin/bash
#
# failure_test.sh - Job that intentionally fails
#
# Purpose: Test error handling and non-zero exit codes
# Expected runtime: < 5 seconds
# Expected exit code: 1

echo "=== Failure Test Job ===" >&2
echo "Job started at: $(date)" >&2
echo "Running on node: $(hostname)" >&2
echo "" >&2

echo "This job is designed to fail for testing purposes" >&2
echo "Simulating error condition..." >&2
sleep 2

echo "" >&2
echo "ERROR: Simulated failure occurred!" >&2
echo "Job failed at: $(date)" >&2

exit 1
