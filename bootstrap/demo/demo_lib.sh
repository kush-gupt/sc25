#!/bin/bash
# Shared library for demo scripts

# Color codes for output
COLOR_RESET="\033[0m"
COLOR_GREEN="\033[32m"
COLOR_BLUE="\033[34m"
COLOR_YELLOW="\033[33m"
COLOR_CYAN="\033[36m"

# Print section header
print_header() {
    local title="$1"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "$title"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
}

# Print demo header
print_demo() {
    local num="$1"
    local title="$2"
    echo ""
    echo "Demo ${num}: ${title}"
}

# Print step with checkmark
print_step() {
    local msg="$1"
    echo "  ✓ ${msg}"
}

# Print warning
print_warning() {
    local msg="$1"
    echo "  ⚠ ${msg}"
}

# Print error
print_error() {
    local msg="$1"
    echo "  ❌ ${msg}"
}

# Print usage examples
print_examples() {
    local scheduler="$1"  # "flux" or "slurm"
    local namespace="$2"
    local pod_info="$3"  # Pod selection info
    
    print_header "Useful Commands for Exploration"
    
    if [ "$scheduler" = "flux" ]; then
        cat <<EOF
Access the MiniCluster:
  POD=\$(kubectl get pods -n $namespace -l job-name=flux-sample -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -it \$POD -n $namespace -c flux-sample -- bash

Monitor jobs (inside pod):
  flux jobs -a           # View all jobs
  flux resource list     # View resources

Submit jobs with dependencies:
  JOB1=\$(flux submit ./script1.sh)
  flux submit --dependency=afterok:\$JOB1 ./script2.sh
EOF
    else  # slurm
        cat <<EOF
Monitor queue:
  kubectl exec -n $namespace $pod_info -- squeue

View job history:
  kubectl exec -n $namespace $pod_info -- sacct

Check job output:
  WORKER=\$(kubectl get pods -n $namespace -l app.kubernetes.io/component=worker -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n $namespace \$WORKER -- cat /tmp/<output_file>.out

View cluster status:
  kubectl exec -n $namespace $pod_info -- sinfo
  kubectl get nodesets -n $namespace
EOF
    fi
    echo ""
}