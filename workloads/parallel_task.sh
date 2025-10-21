#!/bin/bash
# Parallel Task - Simulates distributed computation (MPI-style)
# Performs domain decomposition and local computation
# Usage: parallel_task.sh <rank> <total_ranks>

set -euo pipefail

RANK=${1:-0}
TOTAL_RANKS=${2:-2}

# Input validation
if ! [[ "$RANK" =~ ^[0-9]+$ ]] || ! [[ "$TOTAL_RANKS" =~ ^[0-9]+$ ]]; then
  echo "Error: Rank and total_ranks must be positive integers" >&2
  exit 1
fi

if [ "$RANK" -ge "$TOTAL_RANKS" ]; then
  echo "Error: Rank ($RANK) must be less than total_ranks ($TOTAL_RANKS)" >&2
  exit 1
fi

if [ "$TOTAL_RANKS" -lt 1 ]; then
  echo "Error: total_ranks must be at least 1" >&2
  exit 1
fi

# MPI-like initialization
echo "[MPI] ═══════════════════════════════════════════════════"
echo "[MPI] Parallel Task Execution (MPI + OpenMP Hybrid)"
echo "[MPI] ═══════════════════════════════════════════════════"
echo "[MPI] Process rank: $RANK"
echo "[MPI] Total processes: $TOTAL_RANKS"
echo "[MPI] OpenMP threads per rank: 8"
echo "[MPI] Total domain size: 10 million elements"
echo "[MPI] Hostname: $(hostname)"
echo "[MPI] PID: $$"

# Domain decomposition - divide work among ranks
TOTAL_ELEMENTS=10000000  # 10 million elements
ELEMENTS_PER_RANK=$((TOTAL_ELEMENTS / TOTAL_RANKS))
START=$((RANK * ELEMENTS_PER_RANK))
END=$(((RANK + 1) * ELEMENTS_PER_RANK - 1))

# Handle remainder for last rank
if [ "$RANK" -eq $((TOTAL_RANKS - 1)) ]; then
  END=$((TOTAL_ELEMENTS - 1))
fi

LOCAL_ELEMENTS=$((END - START + 1))

echo "[Rank $RANK] Domain: [$START, $END] (${LOCAL_ELEMENTS} elements)"
echo "[Rank $RANK] Starting local computation..."

START_TIME=$(date +%s)

# Perform local computation with OpenMP-style parallelism
N_THREADS=8
ELEMENTS_TO_PROCESS=$LOCAL_ELEMENTS
ELEMENTS_PER_THREAD=$((ELEMENTS_TO_PROCESS / N_THREADS))

LOCAL_SUM=0
LOCAL_COUNT=0

# Parallel thread execution - each thread processes its assigned domain
for thread in $(seq 0 $((N_THREADS - 1))); do
  THREAD_START=$((START + thread * ELEMENTS_PER_THREAD))
  THREAD_END=$((THREAD_START + ELEMENTS_PER_THREAD - 1))
  
  # Last thread handles remainder
  if [ $thread -eq $((N_THREADS - 1)) ]; then
    THREAD_END=$END
  fi
  
  THREAD_ELEMENTS=$((THREAD_END - THREAD_START + 1))
  echo "[Rank $RANK, Thread $thread] Processing [$THREAD_START, $THREAD_END] ($THREAD_ELEMENTS elements)"
  
  # Each thread performs intensive computation on its elements
  for i in $(seq $THREAD_START $THREAD_END); do
    val=$((i % 1000))
    temp=$((val * val))
    temp2=$((temp / (val + 1)))
    temp3=$((temp2 * val / (val + 2)))
    LOCAL_SUM=$((LOCAL_SUM + temp3))
    LOCAL_COUNT=$((LOCAL_COUNT + 1))
  done
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Calculate statistics
LOCAL_AVG=$(awk -v sum=$LOCAL_SUM -v count=$LOCAL_COUNT 'BEGIN {printf "%.2f", sum/count}')

echo "[Rank $RANK] ─────────────────────────────────────────────"
echo "[Rank $RANK] Local computation complete"
echo "[Rank $RANK] ─────────────────────────────────────────────"
echo "[Rank $RANK] Elements processed: $LOCAL_COUNT"
echo "[Rank $RANK] Local sum: $LOCAL_SUM"
echo "[Rank $RANK] Local average: $LOCAL_AVG"
echo "[Rank $RANK] Computation time: ${ELAPSED}s"
echo "[Rank $RANK] Throughput: $(awk -v n=$LOCAL_COUNT -v t=$ELAPSED 'BEGIN {if(t>0) printf "%.0f", n/t; else print n}') elem/s"

# Root process outputs summary
if [ "$RANK" -eq 0 ]; then
  echo ""
  echo "[Root] ════════════════════════════════════════════════"
  echo "[Root] All tasks completed"
  echo "[Root] MPI_Barrier() and MPI_Reduce() would synchronize here"
  echo "[Root] ════════════════════════════════════════════════"
fi

