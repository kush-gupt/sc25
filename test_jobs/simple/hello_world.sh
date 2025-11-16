#!/bin/bash
#
# hello_world.sh - Basic job script for testing MCP server
#
# Purpose: Validate basic job submission and output retrieval
# Expected runtime: < 5 seconds
# Resources: Minimal (1 node, 1 task)

echo "=== Hello World HPC Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Current user: $(whoami)"
echo "Working directory: $(pwd)"
echo ""
echo "Hello from the HPC cluster!"
echo ""
echo "Job completed at: $(date)"
