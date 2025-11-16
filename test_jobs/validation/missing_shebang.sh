# missing_shebang.sh - Script with missing shebang line
#
# Purpose: Test validation tool's ability to detect missing shebang
# Expected validation: ERROR - missing shebang line
# This script will fail validation and should not be submitted

echo "This script is missing the shebang line (#!/bin/bash)"
echo "It should be caught by the validate_script tool"
echo "Running on node: $(hostname)"
echo "Job started at: $(date)"
