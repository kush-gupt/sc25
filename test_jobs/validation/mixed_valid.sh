#!/bin/bash
#
# mixed_valid.sh - Script with warnings but still runnable
#
# Purpose: Test validation with non-critical warnings
# Expected validation: WARNINGS - suboptimal but valid configuration
# Issues this script should trigger:
#   - References potentially missing modules
#   - Uses deprecated commands
#   - Has suboptimal resource allocation patterns
#
# The script should still be submittable despite warnings

echo "=== Mixed Validation Test ==="
echo "This script has some issues but should still be runnable"
echo "Validation should return warnings, not errors"
echo ""

# Try to load a module that might not exist (warning, not error)
echo "Attempting to load potentially missing module..."
module load nonexistent-module 2>/dev/null || echo "WARNING: Module not found (expected)"

# Use a deprecated command pattern (warning)
echo "Using potentially deprecated pattern..."
cd /tmp && pwd

# Suboptimal loop that could be parallelized (informational)
echo "Running sequential loop (could be optimized)..."
for i in {1..5}; do
    echo "  Iteration $i"
    sleep 1
done

# Reference a path that might not exist (warning)
DATA_PATH="/nonexistent/data/path"
if [ -d "$DATA_PATH" ]; then
    echo "Data path exists: $DATA_PATH"
else
    echo "WARNING: Data path not found: $DATA_PATH"
    echo "Using fallback location"
    DATA_PATH="/tmp"
fi

echo ""
echo "Script completed despite warnings"
echo "Job completed at: $(date)"

exit 0
