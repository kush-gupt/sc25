#!/bin/bash
#
# ml_training_simulation.sh - Simulates a machine learning training workflow
#
# Purpose: Test realistic ML training job with multiple phases
# Expected runtime: ~2 minutes
# Recommended resources: 1 node, 4 tasks, 2GB memory
#
# Phases:
#   1. Data loading and preprocessing
#   2. Model initialization
#   3. Training loop with checkpointing
#   4. Evaluation and results saving

set -e  # Exit on error

echo "=== ML Training Simulation Job ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

# Configuration
MODEL_NAME="test-model-v1"
EPOCHS=5
BATCH_SIZE=32
LEARNING_RATE=0.001
CHECKPOINT_DIR="/tmp/checkpoints_$$"

echo "=== Configuration ==="
echo "Model: $MODEL_NAME"
echo "Epochs: $EPOCHS"
echo "Batch size: $BATCH_SIZE"
echo "Learning rate: $LEARNING_RATE"
echo "Checkpoint directory: $CHECKPOINT_DIR"
echo ""

# Phase 1: Data Loading
echo "=== Phase 1: Data Loading and Preprocessing ==="
echo "[$(date +%T)] Loading training dataset..."
sleep 3
TRAIN_SAMPLES=10000
echo "[$(date +%T)] Loaded $TRAIN_SAMPLES training samples"

echo "[$(date +%T)] Loading validation dataset..."
sleep 2
VAL_SAMPLES=2000
echo "[$(date +%T)] Loaded $VAL_SAMPLES validation samples"

echo "[$(date +%T)] Preprocessing data..."
sleep 3
echo "[$(date +%T)] Data preprocessing complete"
echo ""

# Phase 2: Model Initialization
echo "=== Phase 2: Model Initialization ==="
echo "[$(date +%T)] Initializing model architecture..."
sleep 2
MODEL_PARAMS=1250000
echo "[$(date +%T)] Model initialized with $MODEL_PARAMS parameters"

echo "[$(date +%T)] Setting up optimizer..."
sleep 1
echo "[$(date +%T)] Optimizer configured: Adam (lr=$LEARNING_RATE)"
echo ""

# Create checkpoint directory
mkdir -p "$CHECKPOINT_DIR"

# Phase 3: Training Loop
echo "=== Phase 3: Training Loop ==="
for epoch in $(seq 1 $EPOCHS); do
    echo ""
    echo "--- Epoch $epoch/$EPOCHS ---"
    echo "[$(date +%T)] Starting epoch $epoch"

    # Simulate training batches
    NUM_BATCHES=$((TRAIN_SAMPLES / BATCH_SIZE))
    echo "[$(date +%T)] Processing $NUM_BATCHES batches..."

    # Simulate batch processing (faster than real training)
    sleep 4

    # Calculate simulated metrics
    LOSS=$(echo "scale=4; 2.5 - ($epoch * 0.3) + (0.1 * ($RANDOM % 10) / 10)" | bc 2>/dev/null || echo "1.5")
    ACCURACY=$(echo "scale=2; 60 + ($epoch * 6) + ($RANDOM % 5)" | bc 2>/dev/null || echo "75")

    echo "[$(date +%T)] Epoch $epoch complete"
    echo "  Training loss: $LOSS"
    echo "  Training accuracy: ${ACCURACY}%"

    # Validation
    echo "[$(date +%T)] Running validation..."
    sleep 2
    VAL_LOSS=$(echo "scale=4; 2.7 - ($epoch * 0.25) + (0.1 * ($RANDOM % 10) / 10)" | bc 2>/dev/null || echo "1.7")
    VAL_ACCURACY=$(echo "scale=2; 58 + ($epoch * 5) + ($RANDOM % 5)" | bc 2>/dev/null || echo "72")
    echo "  Validation loss: $VAL_LOSS"
    echo "  Validation accuracy: ${VAL_ACCURACY}%"

    # Checkpointing
    if [ $((epoch % 2)) -eq 0 ]; then
        CHECKPOINT_FILE="$CHECKPOINT_DIR/checkpoint_epoch_${epoch}.pt"
        echo "[$(date +%T)] Saving checkpoint: $CHECKPOINT_FILE"
        cat > "$CHECKPOINT_FILE" << EOF
Checkpoint: Epoch $epoch
Model: $MODEL_NAME
Training Loss: $LOSS
Validation Loss: $VAL_LOSS
Timestamp: $(date)
EOF
        sleep 1
    fi
done

echo ""

# Phase 4: Evaluation and Results
echo "=== Phase 4: Final Evaluation ==="
echo "[$(date +%T)] Running final evaluation on test set..."
sleep 3

TEST_ACCURACY=$(echo "scale=2; 82 + ($RANDOM % 8)" | bc 2>/dev/null || echo "85")
TEST_LOSS="1.234"

echo "[$(date +%T)] Evaluation complete"
echo "  Test accuracy: ${TEST_ACCURACY}%"
echo "  Test loss: $TEST_LOSS"
echo ""

# Save final results
RESULTS_FILE="/tmp/training_results_$$.json"
echo "[$(date +%T)] Saving results to $RESULTS_FILE"
cat > "$RESULTS_FILE" << EOF
{
  "model": "$MODEL_NAME",
  "config": {
    "epochs": $EPOCHS,
    "batch_size": $BATCH_SIZE,
    "learning_rate": $LEARNING_RATE
  },
  "final_metrics": {
    "test_accuracy": $TEST_ACCURACY,
    "test_loss": $TEST_LOSS
  },
  "checkpoints": [
$(ls -1 $CHECKPOINT_DIR | sed 's/^/    "/' | sed 's/$/",/' | sed '$ s/,$//')
  ],
  "completed": "$(date)"
}
EOF

echo ""
echo "=== Training Summary ==="
echo "Model: $MODEL_NAME"
echo "Total epochs: $EPOCHS"
echo "Final test accuracy: ${TEST_ACCURACY}%"
echo "Checkpoints saved: $(ls -1 $CHECKPOINT_DIR | wc -l)"
echo "Results saved to: $RESULTS_FILE"
echo ""

echo "Job completed successfully at: $(date)"

exit 0
