#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/demo_lib.sh"

OCI_REGISTRY="${OCI_REGISTRY:-localhost:5000}"
USE_OCI_ARTIFACTS="${USE_OCI_ARTIFACTS:-true}"
WORKER_PUSH_OUTPUTS="${WORKER_PUSH_OUTPUTS:-false}"
FLUX_NS="flux-operator"
MINICLUSTER_NAME="flux-sample"
FLUX_URI="local:///mnt/flux/view/run/flux/local"

echo "=== Flux Operator Demo ==="

if ! kubectl get crd miniclusters.flux-framework.org >/dev/null 2>&1; then
    print_error "Flux Operator not installed. Run: ./scripts/setup_local_cluster.sh"
    exit 1
fi

kubectl create namespace "${FLUX_NS}" 2>/dev/null || true

flux_exec() {
    kubectl exec -n "${FLUX_NS}" "${POD_NAME}" -c flux-sample -- \
        bash -c "FLUX_URI=${FLUX_URI} $1" 2>/dev/null
}

get_flux_job_info() {
    flux_exec "flux jobs -ano $2 $1" 2>/dev/null || echo ""
}

wait_for_job_data() {
    local max_wait=5 count=0
    while [ $count -lt $max_wait ]; do
        local runtime=$(get_flux_job_info "$1" "{runtime}")
        [ -n "$runtime" ] && [ "$runtime" != "0.0" ] && [ "$runtime" != "0" ] && return 0
        sleep 1; count=$((count + 1))
    done
    return 1
}

create_oci_push_helper() {
    cat > "/tmp/push_to_oci.sh" <<'EOFHELPER'
#!/bin/bash
OCI_REGISTRY="${OCI_REGISTRY:-localhost:5000}"
OCI_OUTPUT_REPO="${OCI_OUTPUT_REPO:-sc25-outputs}"
[ $# -lt 2 ] && echo "Usage: $0 <output_file> <job_id>" >&2 && exit 1
OUTPUT_FILE="$1"; JOB_ID="$2"
command -v podman >/dev/null 2>&1 || exit 0
[ ! -f "$OUTPUT_FILE" ] && exit 0
podman artifact add --file-type text/plain \
    --annotation "job_id=$JOB_ID" --annotation "created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --annotation "hostname=$(hostname)" "${OCI_REGISTRY}/${OCI_OUTPUT_REPO}/job-${JOB_ID}:latest" "$OUTPUT_FILE" 2>&1 && \
    echo "✓ Output archived" >&2
EOFHELPER
    chmod +x "/tmp/push_to_oci.sh"
    kubectl cp "/tmp/push_to_oci.sh" "${FLUX_NS}/${POD_NAME}:/tmp/push_to_oci.sh" -c flux-sample 2>/dev/null
    kubectl exec -n "${FLUX_NS}" "${POD_NAME}" -c flux-sample -- chmod +x /tmp/push_to_oci.sh 2>/dev/null
    rm -f "/tmp/push_to_oci.sh"
}

copy_workload() {
    local tmpfile="/tmp/oci_$1.sh"
    if [ "$USE_OCI_ARTIFACTS" = "true" ] && command -v podman >/dev/null 2>&1 && \
       podman artifact extract "${OCI_REGISTRY}/sc25-workloads/$1:latest" "$tmpfile" 2>/dev/null; then
        kubectl cp "$tmpfile" "${FLUX_NS}/${POD_NAME}:/tmp/$1.sh" -c flux-sample 2>/dev/null
        rm -f "$tmpfile"
    else
        kubectl cp "workloads/$1.sh" "${FLUX_NS}/${POD_NAME}:/tmp/$1.sh" -c flux-sample 2>/dev/null
    fi
    kubectl exec -n "${FLUX_NS}" "${POD_NAME}" -c flux-sample -- chmod +x "/tmp/$1.sh" 2>/dev/null
}

wait_for_flux_resources() {
    echo "⏳ Waiting for Flux broker..."
    local retry=0
    until flux_exec "flux resource list" | grep -q "free.*[1-9]"; do
        [ $retry -ge 30 ] && { flux_exec "flux resource drain" || true; flux_exec "flux resource undrain flux-sample-0" || true; sleep 5; break; }
        echo -n "."; sleep 2; retry=$((retry + 1))
    done
    echo ""
}

echo "Creating MiniCluster..."
cat > /tmp/flux-demo-minicluster.yaml <<EOF
apiVersion: flux-framework.org/v1alpha2
kind: MiniCluster
metadata:
  name: ${MINICLUSTER_NAME}
  namespace: ${FLUX_NS}
spec:
  size: 1
  logging:
    quiet: false
  flux:
    logLevel: 7
  interactive: true
  containers:
    - image: ghcr.io/flux-framework/flux-restful-api:latest
      command: sleep infinity
EOF
kubectl apply -f /tmp/flux-demo-minicluster.yaml
print_step "Deployed"

echo "Waiting for pods..."
sleep 10
kubectl wait --for=condition=Ready pod -l job-name="${MINICLUSTER_NAME}" -n "${FLUX_NS}" --timeout=180s 2>/dev/null || print_warning "Pods still initializing"

POD_NAME=$(kubectl get pods -n "${FLUX_NS}" -l job-name="${MINICLUSTER_NAME}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
[ -z "$POD_NAME" ] && print_error "No pods found" && exit 1

wait_for_flux_resources

build_workload_container() {
    local image_name="localhost/sc25-workload:latest"
    podman image exists "$image_name" 2>/dev/null && echo "  ✓ Container image exists" && return 0
    cd "${SCRIPT_DIR}/../.." || return 1
    if podman build -t "$image_name" -f workloads/Containerfile workloads/ 2>&1 | tail -5; then
        echo "  ✓ Built: $image_name"
        [ "$USE_OCI_ARTIFACTS" = "true" ] && [[ "$OCI_REGISTRY" =~ ^localhost ]] && \
            podman push "$image_name" "${OCI_REGISTRY}/sc25-workload:latest" >/dev/null 2>&1
        return 0
    fi
    return 1
}

if [ "$USE_OCI_ARTIFACTS" = "true" ] && command -v podman >/dev/null 2>&1; then
    echo "📦 OCI Artifact Mode: Enabled (Registry: ${OCI_REGISTRY})"
    [[ "$OCI_REGISTRY" =~ ^localhost ]] && ! curl -s http://localhost:5000/v2/ >/dev/null 2>&1 && \
        podman run -d --name registry -p 5000:5000 --restart=always docker.io/library/registry:2 >/dev/null 2>&1 && sleep 2
    build_workload_container
    pushed=0
    cd "${SCRIPT_DIR}/../.."
    for script in workloads/*.sh; do
        [ -f "$script" ] && podman artifact add --file-type application/x-sh \
            "${OCI_REGISTRY}/sc25-workloads/$(basename "$script" .sh):latest" "$script" >/dev/null 2>&1 && pushed=$((pushed + 1))
    done
    cd - >/dev/null
    echo "  ✓ Pushed $pushed workload scripts"
    [ "$WORKER_PUSH_OUTPUTS" = "true" ] && create_oci_push_helper && echo "  ✓ Worker push enabled"
else
    echo "📂 OCI Mode: Disabled"
fi

flux_exec "flux resource list" || echo "Flux initializing..."
flux_exec "flux run hostname" || true

print_header "Scientific Computing Demos"

print_demo 1 "Monte Carlo Pi Estimation"
copy_workload "monte_carlo"
MC_OUTPUT=$(flux_exec "flux submit --job-name=monte_carlo /tmp/monte_carlo.sh 1000000" 2>&1)
MC_JOB=$(echo "$MC_OUTPUT" | grep -oP 'ƒ\K[A-Za-z0-9]+' || echo "")
if [ -n "$MC_JOB" ]; then
    MC_JOBID="ƒ${MC_JOB}"
    echo "  → Job $MC_JOBID submitted"
    flux_exec "flux job attach $MC_JOBID" >/dev/null 2>&1 || true
    sleep 2
    if wait_for_job_data "$MC_JOBID"; then
        RUNTIME=$(get_flux_job_info "$MC_JOBID" "{runtime}" | awk '{printf "%.2f", $1}')
        echo "  ✓ Completed in ${RUNTIME}s"
    fi
else
    flux_exec "flux run --job-name=monte_carlo /tmp/monte_carlo.sh 1000000" || true
fi

print_demo 2 "Parameter Sweep"
copy_workload "parameter_sweep"
flux_exec "flux run --job-name=param_sweep /tmp/parameter_sweep.sh" || true

print_demo 3 "Molecular Dynamics Parameter Sweep"
copy_workload "md_simulation"
flux_exec 'bash -c "
for temp in 273 300 350 400; do 
  flux run --job-name=MD_T\${temp} /tmp/md_simulation.sh \${temp} 2>&1 | grep -E \"(Final energy|Equilibration)\"
done"' || true

print_demo 4 "Genomics Pipeline (Dependencies)"
copy_workload "genomics_stage1"
copy_workload "genomics_stage2"
copy_workload "genomics_stage3"
flux_exec 'bash -c '\''
JOB1=$(flux submit --job-name=preprocess /tmp/genomics_stage1.sh); 
JOB2=$(flux submit --job-name=qc --dependency=afterok:$JOB1 /tmp/genomics_stage2.sh); 
JOB3=$(flux submit --job-name=analysis --dependency=afterok:$JOB2 /tmp/genomics_stage3.sh); 
echo "  Submitted: $JOB1 → $JOB2 → $JOB3"; 
for i in {1..8}; do 
  sleep 1; 
  flux job wait $JOB3 --timeout=0 2>/dev/null && { echo "✓ Complete"; break; } || true
done; 
flux job attach $JOB3 2>/dev/null | grep -E "(mapped|variants|SNPs|INDELs)" || true
'\''' || true


print_demo 5 "Ensemble Simulation"
copy_workload "ensemble_member"
flux_exec 'bash -c "
for member in 1 2 3 4; do 
  flux run --job-name=ensemble-${member} /tmp/ensemble_member.sh ${member} 2>&1 | grep -E \"(anomaly|temperature|Sea level)\" || true
done"' || true

print_demo 6 "Parallel Tasks"
copy_workload "parallel_task"
flux_exec 'flux run -n 2 --job-name=parallel_tasks bash -c "/tmp/parallel_task.sh \$FLUX_TASK_RANK 2"' || true

print_demo 7 "Drug Screening Array"
copy_workload "drug_screen"
flux_exec 'bash -c "
for i in {1..10}; do flux submit --job-name=drug_screen_\$i /tmp/drug_screen.sh \$i >/dev/null; done
flux queue drain 2>/dev/null || sleep 3
for i in {1..10}; do
  JOBID=\$(flux jobs -a --filter=drug_screen_\$i -no {id} | head -1)
  [ -n \"\$JOBID\" ] && flux job attach \$JOBID 2>/dev/null | grep \"HIT:\" || true
done"' || true

print_header "Job Summary"
flux_exec "flux jobs -a" 2>/dev/null | head -20 || echo "No jobs"
flux_exec "flux resource list" || true

if [ "$USE_OCI_ARTIFACTS" = "true" ] && command -v podman >/dev/null 2>&1; then
    echo "📦 Archiving outputs to OCI..."
    ALL_JOBS=$(flux_exec "flux jobs -a --no-header 2>/dev/null | awk '{print \$1}'" | tr '\n' ' ')
    JOB_COUNT=0
    for JOBID in $ALL_JOBS; do
        TMPFILE="/tmp/flux_job_${JOBID}.txt"
        flux_exec "flux job attach $JOBID 2>/dev/null" > "$TMPFILE" 2>&1 || true
        if [ -s "$TMPFILE" ]; then
            CLEAN_ID=$(echo "$JOBID" | tr -cd 'a-zA-Z0-9-')
            podman artifact add --file-type text/plain "${OCI_REGISTRY}/sc25-outputs/job-flux-${CLEAN_ID}:latest" "$TMPFILE" >/dev/null 2>&1 && JOB_COUNT=$((JOB_COUNT + 1))
        fi
        rm -f "$TMPFILE"
    done
    echo "  ✓ Archived $JOB_COUNT outputs"
fi

print_examples "flux" "${FLUX_NS}" "flux-sample"

read -p "Clean up MiniCluster? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kubectl delete minicluster "${MINICLUSTER_NAME}" -n "${FLUX_NS}" --wait=false && echo "Cleanup initiated"
fi
