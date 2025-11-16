#!/bin/bash
#
# stdout_stderr.sh - Job that writes to both stdout and stderr
#
# Purpose: Test output retrieval for both output streams
# Expected runtime: < 5 seconds
# Resources: Minimal (1 node, 1 task)

echo "=== STDOUT/STDERR Test Job ==="
echo "Job started at: $(date)"

# Write to stdout
echo ""
echo "This message goes to STDOUT (standard output)"
echo "STDOUT: Line 1"
echo "STDOUT: Line 2"
echo "STDOUT: Line 3"

# Write to stderr
echo "" >&2
echo "This message goes to STDERR (standard error)" >&2
echo "STDERR: Warning 1" >&2
echo "STDERR: Warning 2" >&2
echo "STDERR: Warning 3" >&2

# Mix them
echo ""
echo "STDOUT: Processing data..."
sleep 1
echo "STDERR: Non-critical warning during processing" >&2
sleep 1
echo "STDOUT: Processing complete"

echo ""
echo "Job completed at: $(date)"
echo "STDERR: Job finished with warnings" >&2

exit 0
