# Scientific Computing Workloads

Modular workload scripts for **Slurm** and **Flux** schedulers demonstrating HPC patterns.

## Containerized Execution

Workloads run in containers for:
- Worker-side OCI artifact management
- Consistent environment across workers
- Scalability (emulates parallel filesystem at 1000+ worker scale)

## Workloads

**1. Monte Carlo** (`monte_carlo.sh [samples]`) - π estimation via random sampling, 4-thread parallel, default 100M samples

**2. Parameter Sweep** (`parameter_sweep.sh`) - Convergence testing with learning rates (α=0.01-0.5), 50k iterations

**3. Molecular Dynamics** (`md_simulation.sh <temp_K> [steps]`) - Protein simulation, 8-domain decomposition, default 50M steps

**4. Genomics Pipeline** (3 stages) - Alignment → QC → Variant calling, 8-24 parallel threads per stage

**5. Ensemble Simulation** (`ensemble_member.sh <member>`) - CESM2 climate model, 4-component coupling, SSP2-4.5 scenario

**6. Parallel Tasks** (`parallel_task.sh <rank> <total>`) - MPI+OpenMP hybrid, 100M elements, 4 threads/rank

**7. Drug Screening** (`drug_screen.sh [task_id]`) - Molecular docking, 4 parallel conformer search, AutoDock Vina-style

## Usage

**Direct:**
```bash
# Slurm
sbatch --array=1-10 drug_screen.sh
JOB1=$(sbatch genomics_stage1.sh | grep -oP '\d+')
sbatch --dependency=afterok:$JOB1 genomics_stage2.sh

# Flux
for i in {1..10}; do flux submit drug_screen.sh $i; done
JOB1=$(flux submit genomics_stage1.sh)
flux submit --dependency=afterok:$JOB1 genomics_stage2.sh
```

**Containerized:**
```bash
podman build -t sc25-workload -f Containerfile .
sbatch --wrap="podman run --rm sc25-workload /workloads/monte_carlo.sh 1000000"
flux submit podman run --rm sc25-workload /workloads/drug_screen.sh 1
```

**Benefits**: Worker-side OCI artifact management, consistent environment, parallel FS emulation
