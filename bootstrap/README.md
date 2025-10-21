# Bootstrap Scripts

This directory contains scripts for setting up and demonstrating the HPC MCP cluster.

## Setup Scripts

### `setup_local_cluster.sh`

Sets up a local kind cluster with Slurm and/or Flux operators deployed via ArgoCD GitOps.


```bash
# Install both operators via ArgoCD (default)
./setup_local_cluster.sh

# Install only Slurm via ArgoCD
INSTALL_FLUX=false INSTALL_SLURM=true ./setup_local_cluster.sh

# Install only Flux via ArgoCD
INSTALL_FLUX=true INSTALL_SLURM=false ./setup_local_cluster.sh
```

**View Deployed Applications:**
```bash
# List all ArgoCD applications
kubectl get applications -n argocd

# Check Flux operator status
kubectl get application flux-operator -n argocd

# Check Slinky operator status
kubectl get application slurm-operator -n argocd
```

## Demo Scripts

All demonstration and verification scripts are located in the `demo/` subdirectory.

### Slurm Demos

```bash
# Demo Slurm job submission
./demo/demo_slurm_jobs.sh
```

### Flux Demos

```bash
# Demo Flux job submission
./demo/demo_flux_jobs.sh
```

