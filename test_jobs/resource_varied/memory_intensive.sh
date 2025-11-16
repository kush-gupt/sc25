#!/bin/bash
#
# memory_intensive.sh - Memory-intensive job
#
# Purpose: Test memory allocation and monitoring
# Expected runtime: ~20 seconds
# Recommended resources: 1 node, 1 task, 4GB+ memory

echo "=== Memory Intensive Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

# Check available memory
echo "Memory information:"
free -h 2>/dev/null || echo "free command not available"
echo ""

echo "Allocating and processing large data structures..."
echo "This simulates loading large datasets into memory"
echo ""

# Create a large array in memory using Python (if available) or dd
if command -v python3 &> /dev/null; then
    echo "Using Python to allocate ~1GB of memory..."
    python3 << 'EOF'
import sys
import time

# Allocate approximately 1GB of memory
print("Allocating memory...")
data = []
for i in range(10):
    # Each chunk is ~100MB (list of 25 million integers)
    chunk = [i] * 25_000_000
    data.append(chunk)
    print(f"  Allocated {(i+1) * 100}MB...")
    time.sleep(0.5)

print("\nMemory allocated successfully")
print(f"Total items in memory: {sum(len(chunk) for chunk in data):,}")

# Simulate processing
print("\nProcessing data...")
time.sleep(2)
result = sum(sum(chunk) for chunk in data)
print(f"Processing complete. Checksum: {result}")

# Clean up
data = None
print("Memory released")
EOF
else
    echo "Python not available, using alternative method..."
    # Create temporary file-based memory simulation
    TEMP_FILE="/tmp/memory_test_$$"
    dd if=/dev/zero of=$TEMP_FILE bs=1M count=512 2>&1 | grep -v records
    echo "Allocated 512MB temporary file"
    sleep 5
    rm -f $TEMP_FILE
    echo "Memory test completed"
fi

echo ""
echo "Job completed at: $(date)"
