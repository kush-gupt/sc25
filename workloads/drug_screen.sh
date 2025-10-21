#!/bin/bash
# High-throughput drug screening simulation
# Simulates molecular docking for drug discovery using AutoDock-style scoring
# Usage: drug_screen.sh [task_id]

set -euo pipefail

# Support both Slurm and Flux array job variables
TASK_ID=${SLURM_ARRAY_TASK_ID:-${1:-1}}

# Input validation
if ! [[ "$TASK_ID" =~ ^[0-9]+$ ]]; then
  echo "Error: Task ID must be a positive integer" >&2
  exit 1
fi

COMPOUND_ID=$((1000 + TASK_ID))

echo "[Screening] ════════════════════════════════════════════"
echo "[Screening] High-Throughput Drug Screening"
echo "[Screening] ════════════════════════════════════════════"
echo "[Screening] Task ID: $TASK_ID"
echo "[Screening] Compound ID: CPD-${COMPOUND_ID}"
echo "[Screening] Hostname: $(hostname)"
echo "[Screening] Target protein: SARS-CoV-2 Mpro (Main Protease)"
echo "[Screening] Method: Molecular docking (AutoDock Vina)"
echo "[Screening] Grid resolution: 1M points across 8 conformers"

echo "[Screening] Computing docking scores with parallel conformer search..."
# Perform grid-based search and energy calculation with parallel conformer generation
RESULT=$(awk -v id=$COMPOUND_ID 'BEGIN {
  srand(id);
  
  # Parallel conformer search
  n_conformers = 8;
  best_energy = 999999;
  grid_points_per_conformer = 125000;
  
  # Parallel conformer evaluation
  for(conformer=0; conformer<n_conformers; conformer++) {
    conformer_seed = id + conformer * 10000;
    srand(conformer_seed);
    conformer_best = 999999;
    
    # Grid search for this conformer
    for(trial=1; trial<=grid_points_per_conformer; trial++) {
      # Random pose in binding pocket
      x = rand() * 10 - 5;
      y = rand() * 10 - 5;
      z = rand() * 10 - 5;
      theta = rand() * 6.28;
      
      # Calculate energy components for this pose
      r = sqrt(x*x + y*y + z*z) + 3.5;  # Offset to keep distances realistic
      
      # Lennard-Jones potential (van der Waals) - attractive component with distance-dependent weighting
      sigma = 3.8;
      epsilon = 1.2;
      vdw_trial = 4 * epsilon * ((sigma/r)^12 - (sigma/r)^6);
      
      # Add distance-dependent correction
      if(r < 5.0) vdw_trial *= (1.0 + 0.05 * (5.0 - r));
      
      # Electrostatic (Coulomb) - main contributor to binding
      q1 = 1.0 + rand() * 0.5;
      q2 = -(0.8 + rand() * 0.7);
      elec_trial = 22 * q1 * q2 / r;
      
      # Hydrogen bonding (geometry and distance dependent) - significant contribution
      hbond_trial = 0;
      if(r < 4.5 && r > 2.8 && cos(theta) < -0.2) {
        hbond_trial = -(3.0 + rand() * 3.0);
      }
      
      # Desolvation penalty (positive, opposes binding) - smaller penalty
      desolv_trial = 0.5 + rand() * 1.0;
      
      # Total trial energy
      trial_energy = vdw_trial + elec_trial + hbond_trial + desolv_trial;
      
      if(trial_energy < conformer_best) {
        conformer_best = trial_energy;
        if(trial_energy < best_energy) {
          best_energy = trial_energy;
          best_vdw = vdw_trial;
          best_elec = elec_trial;
          best_hbond = hbond_trial;
          best_desolv = desolv_trial;
        }
      }
    }
  }
  
  # Torsional penalty (increases final energy, reducing hits)
  torsion = 3.0 + rand() * 4.0;
  binding_energy = best_energy + torsion;
  
  # Additional metrics
  heavy_atoms = 20 + int(rand() * 30);
  lig_eff = binding_energy / heavy_atoms;
  num_hbonds = int(1 + rand() * 5);
  rmsd = 0.5 + rand() * 2.0;
  
  printf "%.3f,%.2f,%.2f,%.2f,%.2f,%.2f,%d,%.3f,%.2f", 
         binding_energy, best_vdw, best_elec, best_hbond, best_desolv, lig_eff, num_hbonds, rmsd, torsion;
}')

IFS=, read BINDING_ENERGY VDW ELEC HBOND DESOLV LIG_EFF NUM_HBONDS RMSD TORSION <<< "$RESULT"

# Output results
echo ""
echo "[Screening] ════════════════════════════════════════════"
echo "[Screening] Docking Results - CPD-${COMPOUND_ID}"
echo "[Screening] ════════════════════════════════════════════"
echo "[Screening] Binding energy: ${BINDING_ENERGY} kcal/mol"
echo "[Screening] ────────────────────────────────────────────"
echo "[Screening] Energy components:"
echo "[Screening]   • van der Waals:    ${VDW} kcal/mol"
echo "[Screening]   • Electrostatic:    ${ELEC} kcal/mol"
echo "[Screening]   • H-bonds:          ${HBOND} kcal/mol"
echo "[Screening]   • Desolvation:      ${DESOLV} kcal/mol"
echo "[Screening]   • Torsional:        ${TORSION} kcal/mol"
echo "[Screening] ────────────────────────────────────────────"
echo "[Screening] Ligand efficiency: ${LIG_EFF} kcal/mol"
echo "[Screening] H-bond count: ${NUM_HBONDS}"
echo "[Screening] RMSD best pose: ${RMSD} Å"

# Check if compound is a hit (strong binder)
# Typical thresholds: < -10.0 kcal/mol is a strong hit
IS_HIT=$(awk -v energy=$BINDING_ENERGY 'BEGIN {
  if (energy < -10.0) print "1";
  else print "0";
}')

echo ""
if [ "$IS_HIT" = "1" ]; then
  echo "[Screening] ⭐ HIT: Strong binder detected! (< -10.0 kcal/mol)"
  echo "[Screening] Recommendation: Proceed to experimental validation"
else
  echo "[Screening] Classification: Weak interaction"
  echo "[Screening] Recommendation: Deprioritize for further study"
fi
echo "[Screening] ✓ Screening complete"

