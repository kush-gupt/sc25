#!/bin/bash
#
# data_preprocessing.sh - Multi-stage data preprocessing pipeline
#
# Purpose: Test realistic data pipeline workflow
# Expected runtime: ~90 seconds
# Recommended resources: 1 node, 2 tasks, 1GB memory
#
# Pipeline stages:
#   1. Data ingestion from multiple sources
#   2. Data cleaning and validation
#   3. Feature extraction and transformation
#   4. Data splitting and export

set -e  # Exit on error

echo "=== Data Preprocessing Pipeline ==="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo ""

# Configuration
PIPELINE_ID="preprocessing_$$"
WORK_DIR="/tmp/data_pipeline_$PIPELINE_ID"
OUTPUT_DIR="$WORK_DIR/output"

echo "=== Pipeline Configuration ==="
echo "Pipeline ID: $PIPELINE_ID"
echo "Working directory: $WORK_DIR"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Setup working directories
mkdir -p "$WORK_DIR"/{raw,cleaned,processed,output}

# Stage 1: Data Ingestion
echo "=== Stage 1: Data Ingestion ==="
echo "[$(date +%T)] Ingesting data from multiple sources..."

echo "[$(date +%T)] Source 1: Downloading sensor data..."
sleep 3
SENSOR_RECORDS=5000
echo "timestamp,sensor_id,temperature,humidity" > "$WORK_DIR/raw/sensors.csv"
for i in $(seq 1 100); do
    echo "2025-01-15T10:$((i % 60)):00,sensor_$i,$((20 + RANDOM % 15)),$((40 + RANDOM % 40))" >> "$WORK_DIR/raw/sensors.csv"
done
echo "[$(date +%T)] Downloaded $SENSOR_RECORDS sensor records"

echo "[$(date +%T)] Source 2: Loading user events..."
sleep 2
USER_EVENTS=3000
echo "event_id,user_id,event_type,timestamp" > "$WORK_DIR/raw/events.csv"
for i in $(seq 1 100); do
    echo "evt_$i,user_$((RANDOM % 50)),click,2025-01-15T10:$((i % 60)):00" >> "$WORK_DIR/raw/events.csv"
done
echo "[$(date +%T)] Loaded $USER_EVENTS user events"

echo "[$(date +%T)] Source 3: Fetching logs..."
sleep 2
LOG_ENTRIES=8000
echo "[$(date +%T)] Fetched $LOG_ENTRIES log entries"

TOTAL_RECORDS=$((SENSOR_RECORDS + USER_EVENTS + LOG_ENTRIES))
echo "[$(date +%T)] Total records ingested: $TOTAL_RECORDS"
echo ""

# Stage 2: Data Cleaning
echo "=== Stage 2: Data Cleaning and Validation ==="
echo "[$(date +%T)] Validating data schemas..."
sleep 2
echo "[$(date +%T)] Schema validation complete - all fields valid"

echo "[$(date +%T)] Checking for missing values..."
sleep 2
MISSING_VALUES=127
echo "[$(date +%T)] Found $MISSING_VALUES missing values - applying imputation"
sleep 2
echo "[$(date +%T)] Imputation complete"

echo "[$(date +%T)] Detecting outliers..."
sleep 2
OUTLIERS=43
echo "[$(date +%T)] Detected $OUTLIERS outliers - flagged for review"

echo "[$(date +%T)] Removing duplicates..."
sleep 1
DUPLICATES=89
CLEANED_RECORDS=$((TOTAL_RECORDS - DUPLICATES))
echo "[$(date +%T)] Removed $DUPLICATES duplicate records"
echo "[$(date +%T)] Cleaned dataset size: $CLEANED_RECORDS records"

# Save cleaned data
cp "$WORK_DIR/raw/sensors.csv" "$WORK_DIR/cleaned/sensors_clean.csv"
cp "$WORK_DIR/raw/events.csv" "$WORK_DIR/cleaned/events_clean.csv"
echo ""

# Stage 3: Feature Extraction
echo "=== Stage 3: Feature Extraction and Transformation ==="
echo "[$(date +%T)] Extracting temporal features..."
sleep 3
echo "[$(date +%T)] Created features: hour_of_day, day_of_week, is_weekend"

echo "[$(date +%T)] Computing statistical aggregations..."
sleep 3
echo "[$(date +%T)] Computed: rolling_avg, rolling_std, percentile_rank"

echo "[$(date +%T)] Applying transformations..."
sleep 2
echo "[$(date +%T)] Applied: log_transform, min_max_scaling, one_hot_encoding"

echo "[$(date +%T)] Generating derived features..."
sleep 2
NEW_FEATURES=45
echo "[$(date +%T)] Generated $NEW_FEATURES derived features"

# Create feature summary
cat > "$WORK_DIR/processed/feature_summary.txt" << EOF
Feature Extraction Summary
==========================
Original features: 12
Temporal features: 8
Statistical features: 12
Transformed features: 13
Derived features: $NEW_FEATURES
Total features: $((12 + 8 + 12 + 13 + NEW_FEATURES))

Completed: $(date)
EOF

echo ""

# Stage 4: Data Splitting and Export
echo "=== Stage 4: Data Splitting and Export ==="
echo "[$(date +%T)] Splitting data into train/validation/test sets..."
sleep 2

TRAIN_SIZE=$((CLEANED_RECORDS * 70 / 100))
VAL_SIZE=$((CLEANED_RECORDS * 15 / 100))
TEST_SIZE=$((CLEANED_RECORDS * 15 / 100))

echo "[$(date +%T)] Split complete:"
echo "  Training set: $TRAIN_SIZE records (70%)"
echo "  Validation set: $VAL_SIZE records (15%)"
echo "  Test set: $TEST_SIZE records (15%)"

echo "[$(date +%T)] Exporting processed datasets..."
sleep 3

# Create mock output files
touch "$OUTPUT_DIR/train.parquet"
touch "$OUTPUT_DIR/validation.parquet"
touch "$OUTPUT_DIR/test.parquet"

echo "[$(date +%T)] Generating metadata..."
cat > "$OUTPUT_DIR/metadata.json" << EOF
{
  "pipeline_id": "$PIPELINE_ID",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "input_records": $TOTAL_RECORDS,
  "output_records": $CLEANED_RECORDS,
  "splits": {
    "train": $TRAIN_SIZE,
    "validation": $VAL_SIZE,
    "test": $TEST_SIZE
  },
  "features": $((12 + 8 + 12 + 13 + NEW_FEATURES)),
  "quality_metrics": {
    "missing_values_imputed": $MISSING_VALUES,
    "outliers_detected": $OUTLIERS,
    "duplicates_removed": $DUPLICATES
  }
}
EOF

echo "[$(date +%T)] Creating data quality report..."
cat > "$OUTPUT_DIR/quality_report.txt" << EOF
Data Quality Report
===================
Pipeline: $PIPELINE_ID
Date: $(date)

Input Data:
  - Total records: $TOTAL_RECORDS
  - Sources: 3

Data Cleaning:
  - Missing values imputed: $MISSING_VALUES
  - Outliers detected: $OUTLIERS
  - Duplicates removed: $DUPLICATES
  - Clean records: $CLEANED_RECORDS

Feature Engineering:
  - Total features: $((12 + 8 + 12 + 13 + NEW_FEATURES))
  - New features created: $((8 + 12 + 13 + NEW_FEATURES))

Output Splits:
  - Training: $TRAIN_SIZE (70%)
  - Validation: $VAL_SIZE (15%)
  - Test: $TEST_SIZE (15%)

Status: SUCCESS
EOF

sleep 1
echo ""

# Final Summary
echo "=== Pipeline Summary ==="
echo "Pipeline ID: $PIPELINE_ID"
echo "Total processing time: ~90 seconds"
echo "Records processed: $TOTAL_RECORDS → $CLEANED_RECORDS"
echo "Features generated: $((12 + 8 + 12 + 13 + NEW_FEATURES))"
echo "Output files:"
ls -lh "$OUTPUT_DIR" | tail -n +2 | awk '{print "  - " $9 " (" $5 ")"}'
echo ""
echo "All outputs saved to: $OUTPUT_DIR"
echo ""

echo "Job completed successfully at: $(date)"

exit 0
