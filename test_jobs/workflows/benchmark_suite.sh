#!/bin/bash
#
# benchmark_suite.sh - Comprehensive benchmark suite
#
# Purpose: Test job with multiple benchmark phases
# Expected runtime: ~2 minutes
# Recommended resources: 1 node, 4 tasks, 2 CPUs per task
#
# Benchmark phases:
#   1. CPU performance (compute-intensive)
#   2. Memory bandwidth
#   3. I/O throughput
#   4. Network latency (if multi-node)

set -e  # Exit on error

echo "=== HPC Benchmark Suite ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

# System information
echo "=== System Information ==="
echo "Hostname: $(hostname)"
echo "CPU cores: $(nproc)"
echo "Memory: $(free -h 2>/dev/null | grep Mem | awk '{print $2}' || echo 'N/A')"
echo "OS: $(uname -s) $(uname -r)"
echo ""

RESULTS_FILE="/tmp/benchmark_results_$$.txt"

# Start results file
cat > "$RESULTS_FILE" << EOF
HPC Benchmark Suite Results
===========================
Hostname: $(hostname)
Date: $(date)
CPU Cores: $(nproc)

EOF

# Benchmark 1: CPU Performance
echo "=== Benchmark 1: CPU Performance ==="
echo "Running CPU-intensive computation..."
echo ""

echo "Test 1.1: Integer arithmetic"
START_TIME=$(date +%s)
RESULT=0
for i in {1..1000000}; do
    RESULT=$((RESULT + i))
done
END_TIME=$(date +%s)
CPU_INT_TIME=$((END_TIME - START_TIME))
echo "  Integer operations: ${CPU_INT_TIME}s (processed 1M iterations)"

echo "Test 1.2: Floating point computation"
START_TIME=$(date +%s)
if command -v bc &> /dev/null; then
    RESULT=$(seq 1 100000 | awk '{sum += sqrt($1)} END {print sum}')
    END_TIME=$(date +%s)
    CPU_FLOAT_TIME=$((END_TIME - START_TIME))
    echo "  Floating point operations: ${CPU_FLOAT_TIME}s (computed 100K square roots)"
else
    echo "  bc not available, skipping float test"
    CPU_FLOAT_TIME="N/A"
fi

echo "Test 1.3: Parallel CPU test"
START_TIME=$(date +%s)
for i in {1..4}; do
    {
        count=0
        for j in {1..500000}; do
            count=$((count + 1))
        done
    } &
done
wait
END_TIME=$(date +%s)
CPU_PARALLEL_TIME=$((END_TIME - START_TIME))
echo "  Parallel execution (4 cores): ${CPU_PARALLEL_TIME}s"

cat >> "$RESULTS_FILE" << EOF
CPU Benchmarks:
  Integer operations: ${CPU_INT_TIME}s
  Floating point ops: ${CPU_FLOAT_TIME}s
  Parallel execution: ${CPU_PARALLEL_TIME}s

EOF

echo ""

# Benchmark 2: Memory Performance
echo "=== Benchmark 2: Memory Bandwidth ==="
echo "Testing memory allocation and access patterns..."
echo ""

if command -v python3 &> /dev/null; then
    echo "Test 2.1: Sequential memory access"
    START_TIME=$(date +%s)
    python3 << 'PYEOF'
import time
# Allocate 100MB of memory
data = [i for i in range(12500000)]  # 100MB of integers
# Sequential access
total = sum(data)
print(f"  Allocated and summed 100MB of data")
PYEOF
    END_TIME=$(date +%s)
    MEM_SEQ_TIME=$((END_TIME - START_TIME))
    echo "  Sequential access time: ${MEM_SEQ_TIME}s"

    echo "Test 2.2: Random memory access"
    START_TIME=$(date +%s)
    python3 << 'PYEOF'
import random
# Allocate and randomly access
data = [i for i in range(12500000)]
indices = [random.randint(0, len(data)-1) for _ in range(1000000)]
total = sum(data[i] for i in indices)
print(f"  Random access completed (1M accesses)")
PYEOF
    END_TIME=$(date +%s)
    MEM_RAND_TIME=$((END_TIME - START_TIME))
    echo "  Random access time: ${MEM_RAND_TIME}s"

    cat >> "$RESULTS_FILE" << EOF
Memory Benchmarks:
  Sequential access: ${MEM_SEQ_TIME}s (100MB)
  Random access: ${MEM_RAND_TIME}s (1M accesses)

EOF
else
    echo "  Python3 not available, skipping memory tests"
    cat >> "$RESULTS_FILE" << EOF
Memory Benchmarks:
  Skipped (Python3 not available)

EOF
fi

echo ""

# Benchmark 3: I/O Performance
echo "=== Benchmark 3: I/O Throughput ==="
echo "Testing filesystem I/O performance..."
echo ""

TEST_FILE="/tmp/io_benchmark_$$.dat"

echo "Test 3.1: Sequential write"
START_TIME=$(date +%s)
dd if=/dev/zero of="$TEST_FILE" bs=1M count=100 2>&1 | grep -v records
END_TIME=$(date +%s)
IO_WRITE_TIME=$((END_TIME - START_TIME))
WRITE_SPEED=$(echo "scale=2; 100 / $IO_WRITE_TIME" | bc 2>/dev/null || echo "N/A")
echo "  Write performance: ${WRITE_SPEED} MB/s"

echo "Test 3.2: Sequential read"
START_TIME=$(date +%s)
dd if="$TEST_FILE" of=/dev/null bs=1M 2>&1 | grep -v records
END_TIME=$(date +%s)
IO_READ_TIME=$((END_TIME - START_TIME))
READ_SPEED=$(echo "scale=2; 100 / $IO_READ_TIME" | bc 2>/dev/null || echo "N/A")
echo "  Read performance: ${READ_SPEED} MB/s"

rm -f "$TEST_FILE"

cat >> "$RESULTS_FILE" << EOF
I/O Benchmarks:
  Sequential write: ${WRITE_SPEED} MB/s
  Sequential read: ${READ_SPEED} MB/s

EOF

echo ""

# Benchmark 4: Network (if applicable)
echo "=== Benchmark 4: Network Latency ==="
if [ -n "$SLURM_JOB_NUM_NODES" ] && [ "$SLURM_JOB_NUM_NODES" -gt 1 ]; then
    echo "Multi-node job detected, testing inter-node latency..."
    # This would require actual multi-node setup
    echo "  Inter-node ping test: N/A (requires MPI setup)"
    NETWORK_RESULT="Multi-node (test skipped)"
else
    echo "Single-node job, testing loopback latency..."
    if command -v ping &> /dev/null; then
        PING_RESULT=$(ping -c 5 localhost 2>&1 | grep avg | awk -F'/' '{print $5}')
        echo "  Loopback latency: ${PING_RESULT}ms average"
        NETWORK_RESULT="${PING_RESULT}ms (loopback)"
    else
        echo "  ping command not available"
        NETWORK_RESULT="N/A"
    fi
fi

cat >> "$RESULTS_FILE" << EOF
Network Benchmarks:
  Latency: $NETWORK_RESULT

EOF

echo ""

# Generate summary
echo "=== Benchmark Summary ==="
cat >> "$RESULTS_FILE" << EOF
====================================
Summary:
  All benchmarks completed successfully
  Results saved to: $RESULTS_FILE
  Completed: $(date)
EOF

cat "$RESULTS_FILE"
echo ""
echo "Detailed results saved to: $RESULTS_FILE"
echo ""

echo "Job completed successfully at: $(date)"

exit 0
