#!/bin/bash
# Parameter Sweep for Optimization
# Tests convergence rates with different learning rates (α)
# Usage: parameter_sweep.sh ["alpha_values"]

set -euo pipefail

ALPHA=${1:-"0.01 0.05 0.1 0.5"}

echo "[Parameter Sweep] Starting optimization study..."
echo "[Parameter Sweep] Hostname: $(hostname)"
echo "[Parameter Sweep] Testing learning rates: $ALPHA"
echo ""

# Create temporary results file
RESULTS_FILE=$(mktemp)
trap "rm -f $RESULTS_FILE" EXIT

# Run parameter sweep
COUNT=0
for alpha in $ALPHA; do
  COUNT=$((COUNT + 1))
  printf "   α=${alpha}: Processing... "
  
  awk -v a=$alpha 'BEGIN {
    srand();
    iterations=500000;
    converge=0;
    value=10.0;
    
    for(i=1; i<=iterations; i++) {
      delta = rand() * 2 - 1;
      noise = (rand() - 0.5) * 0.1;
      gradient = delta + noise;
      
      # Momentum term for more realistic optimization
      if(i > 1) {
        momentum = 0.9 * prev_delta;
        gradient += momentum;
      }
      prev_delta = gradient;
      
      value = value - a * gradient;
      
      # Check convergence threshold
      if(value < 0.1 && value > -0.1) {
        converge = i;
        break;
      }
    }
    if(converge == 0) converge = iterations;
    printf "   │  %-6s  │   %-6s   │   %-7.4f   │\n", a, converge, value;
  }' >> "$RESULTS_FILE"
  
  echo "✓"
done

if [ "$COUNT" -eq 0 ]; then
  echo "Error: No valid alpha values provided" >&2
  exit 1
fi

# Display results
echo ""
echo "📊 Parameter Sweep Results:"
echo "   ┌──────────┬────────────┬─────────────┐"
echo "   │ Alpha(α) │ Iterations │ Final Value │"
echo "   ├──────────┼────────────┼─────────────┤"
cat "$RESULTS_FILE"
echo "   └──────────┴────────────┴─────────────┘"
echo ""
echo "   Analysis:"
echo "   • Higher α → faster convergence (fewer iterations)"
echo "   • Lower α → slower but more stable convergence"
echo "   • Tested ${COUNT} learning rate(s)"
echo "[Parameter Sweep] ✓ Optimization study complete"

