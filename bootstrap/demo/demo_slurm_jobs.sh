#!/bin/bash
# Slurm job submission demo
# https://github.com/SlinkyProject/slurm-operator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/demo_lib.sh"

OCI_REGISTRY="${OCI_REGISTRY:-localhost:5000}"
USE_OCI_ARTIFACTS="${USE_OCI_ARTIFACTS:-true}"
WORKER_PUSH_OUTPUTS="${WORKER_PUSH_OUTPUTS:-true}"
SLURM_NS="${SLURM_NAMESPACE:-slurm}"
SSH_PORT="${SLURM_SSH_PORT:-2222}"
SSH_HOST="${SLURM_SSH_HOST:-localhost}"
SSH_USER="${SLURM_SSH_USER:-root}"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

LOGIN_POD=$(kubectl get pods -n "$SLURM_NS" -l app.kubernetes.io/component=login -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$LOGIN_POD" ] && print_error "Slurm login service not found in namespace '$SLURM_NS'" && exit 1

if ! ssh ${SSH_OPTS} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} "echo 'ok'" >/dev/null 2>&1; then
    print_error "Cannot connect to SSH at ${SSH_USER}@${SSH_HOST}:${SSH_PORT}"
    exit 1
fi

echo "✓ Connected to Slurm: ${SSH_USER}@${SSH_HOST}:${SSH_PORT}"

slurm_exec() { ssh ${SSH_OPTS} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} "$@"; }

read_output() {
    local worker_pod=$(kubectl get pods -n "$SLURM_NS" -l app.kubernetes.io/component=worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    [ -n "$worker_pod" ] && kubectl exec -n "$SLURM_NS" "$worker_pod" -c slurmd -- cat "$1" 2>/dev/null || true
}

save_output_to_oci() {
    [ "$USE_OCI_ARTIFACTS" != "true" ] && return 0
    command -v podman >/dev/null 2>&1 || return 0
    local tmpfile="/tmp/job_output_$2.txt"
    read_output "$1" > "$tmpfile" 2>/dev/null || return 0
    local job_annotation=""
    [ -n "$3" ] && job_annotation="--annotation job_id=$3"
    [ -s "$tmpfile" ] && podman artifact add --file-type text/plain $job_annotation "${OCI_REGISTRY}/sc25-outputs/job-$2:latest" "$tmpfile" >/dev/null 2>&1
    rm -f "$tmpfile"
}

create_oci_push_helper() {
    cat > "/tmp/push_to_oci.sh" <<'EOFHELPER'
#!/bin/bash
OCI_REGISTRY="${OCI_REGISTRY:-localhost:5000}"
OCI_OUTPUT_REPO="${OCI_OUTPUT_REPO:-sc25-outputs}"
[ $# -lt 2 ] && echo "Usage: $0 <output_file> <job_id>" >&2 && exit 1
command -v podman >/dev/null 2>&1 || exit 0
[ ! -f "$1" ] && exit 0
podman artifact add --file-type text/plain --annotation "job_id=$2" \
    "${OCI_REGISTRY}/${OCI_OUTPUT_REPO}/job-$2:latest" "$1" 2>&1 && echo "✓ Archived" >&2
EOFHELPER
    chmod +x "/tmp/push_to_oci.sh"
    scp ${SSH_OPTS} -P ${SSH_PORT} "/tmp/push_to_oci.sh" "${SSH_USER}@${SSH_HOST}:/tmp/" 2>&1 | grep -v "Transferred" || true
    ssh ${SSH_OPTS} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} "chmod +x /tmp/push_to_oci.sh" 2>/dev/null || true
    rm -f "/tmp/push_to_oci.sh"
}

copy_workload_to_all() {
    local tmpfile="/tmp/oci_$1.sh"
    if [ "$USE_OCI_ARTIFACTS" = "true" ] && command -v podman >/dev/null 2>&1 && \
       podman artifact extract "${OCI_REGISTRY}/sc25-workloads/$1:latest" "$tmpfile" 2>/dev/null; then
        scp ${SSH_OPTS} -P ${SSH_PORT} "$tmpfile" "${SSH_USER}@${SSH_HOST}:/tmp/$1.sh" 2>&1 | grep -v "Transferred" || true
        rm -f "$tmpfile"
    else
        scp ${SSH_OPTS} -P ${SSH_PORT} "${SCRIPT_DIR}/../../workloads/$1.sh" "${SSH_USER}@${SSH_HOST}:/tmp/$1.sh" 2>&1 | grep -v "Transferred" || true
    fi
    ssh ${SSH_OPTS} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} "chmod +x /tmp/$1.sh" 2>/dev/null || true
}

build_workload_container() {
    local image_name="localhost/sc25-workload:latest"
    podman image exists "$image_name" 2>/dev/null && echo "  ✓ Container exists" && return 0
    cd "${SCRIPT_DIR}/../.." || return 1
    if podman build -t "$image_name" -f workloads/Containerfile workloads/ 2>&1 | tail -5; then
        echo "  ✓ Built: $image_name"
        [ "$USE_OCI_ARTIFACTS" = "true" ] && [[ "$OCI_REGISTRY" =~ ^localhost ]] && \
            podman push "$image_name" "${OCI_REGISTRY}/sc25-workload:latest" >/dev/null 2>&1
        return 0
    fi
    return 1
}

setup_workloads() {
    if [ "$USE_OCI_ARTIFACTS" = "true" ] && command -v podman >/dev/null 2>&1; then
        echo "📦 OCI Mode: Enabled (Registry: ${OCI_REGISTRY})"
        [[ "$OCI_REGISTRY" =~ ^localhost ]] && ! curl -s http://localhost:5000/v2/ >/dev/null 2>&1 && \
            podman run -d --name registry -p 5000:5000 --restart=always docker.io/library/registry:2 >/dev/null 2>&1 && sleep 2
        build_workload_container
        local pushed=0
        for script in "${SCRIPT_DIR}/../../workloads"/*.sh; do
            [ -f "$script" ] && podman artifact add --file-type application/x-sh \
                "${OCI_REGISTRY}/sc25-workloads/$(basename "$script" .sh):latest" "$script" >/dev/null 2>&1 && pushed=$((pushed + 1))
        done
        echo "  ✓ Pushed $pushed scripts"
        [ "$WORKER_PUSH_OUTPUTS" = "true" ] && create_oci_push_helper && echo "  ✓ Worker push enabled"
    else
        echo "📂 OCI Mode: Disabled"
    fi
    
    for script in monte_carlo parameter_sweep genomics_stage{1,2,3} ensemble_member md_simulation parallel_task drug_screen; do
        [ -f "${SCRIPT_DIR}/../../workloads/${script}.sh" ] && copy_workload_to_all "$script"
    done
    slurm_exec "chmod +x /tmp/*.sh 2>/dev/null" || true
    print_step "Workloads ready"
}

get_job_counts() {
    local running=$(slurm_exec squeue -j "$1" -h -t RUNNING 2>/dev/null | wc -l)
    local pending=$(slurm_exec squeue -j "$1" -h -t PENDING 2>/dev/null | wc -l)
    echo "$running $pending"
}

monitor_slurm_jobs() {
    for i in $(seq 1 "$3"); do
        local counts=$(get_job_counts "$1")
        read -r running pending <<< "$counts"
        printf "\r\033[K   [t+%ds] Running: %d | Pending: %d | Done: %d/%d" \
            "$i" "$running" "$pending" "$(($2 - running - pending))" "$2"
        [ "$running" -eq 0 ] && [ "$pending" -eq 0 ] && break
        sleep 1
    done
    printf "\n"
}

release_held_jobs() {
    local held=$(slurm_exec squeue -j "$1" -h -t PENDING -o "%i %r" 2>/dev/null | grep -i "held" | awk '{print $1}' || true)
    [ -n "$held" ] && for job in $held; do slurm_exec scontrol release "$job" 2>/dev/null || true; done
}

setup_workloads

echo "=== Slurm Job Demo ==="
ACCOUNTING_ENABLED=false
if slurm_exec sacct --noheader -n 2>&1 | head -1 | grep -qE '^[0-9]'; then
    ACCOUNTING_ENABLED=true
fi
[ "$ACCOUNTING_ENABLED" = true ] && echo "✓ Accounting enabled" || echo "ℹ️ Accounting disabled"

slurm_exec sinfo

print_header "Demos"

print_demo 1 "Interactive Job (srun hostname)"
slurm_exec srun hostname

print_demo 2 "Monte Carlo Array (4 tasks)"
JOB1=$(slurm_exec sbatch --array=1-4 --output=/tmp/monte_carlo_%a.out /tmp/monte_carlo.sh 2000000 2>/dev/null | grep -oP '\d+' || echo "")
[ -n "$JOB1" ] && echo "  → Job $JOB1 submitted" || echo "  ⚠ Job submission failed"
[ -n "$JOB1" ] && monitor_slurm_jobs "$JOB1" 4 30
sleep 2
for task in 1 2 3 4; do
    read_output /tmp/monte_carlo_${task}.out 2>/dev/null | grep -E "(Estimated|Error)" 2>/dev/null | head -2 || true
done
if [ "$USE_OCI_ARTIFACTS" = "true" ] && [ -n "$JOB1" ]; then
    printf "  📦 Artifacting"
    for task in 1 2 3 4; do save_output_to_oci "/tmp/monte_carlo_${task}.out" "mc-array-${task}" "${JOB1}_${task}" && printf "."; done
    echo " ✓"
fi

if [ "$ACCOUNTING_ENABLED" = true ] && [ -n "$JOB1" ]; then
    echo -e "\nJobID | State | Elapsed | CPUTime"
    slurm_exec sacct -j "$JOB1" --format=JobID,State,Elapsed,CPUTime -P -n 2>/dev/null | grep -v "extern\|batch" || true
fi

print_demo 3 "MD Parameter Sweep"
MD_JOBS="" PREV_JOB=""
for temp in 273 300 350 400; do
    JOB=$(slurm_exec sbatch ${PREV_JOB:+--dependency=afterok:$PREV_JOB} --job-name=MD_T${temp} --output=/tmp/md_${temp}.out /tmp/md_simulation.sh $temp 5000000 2>/dev/null | grep -oP '\d+' || echo "")
    [ -n "$JOB" ] && echo "  → Job $JOB (T=${temp}K)" || echo "  ⚠ Job $temp failed"
    [ -n "$JOB" ] && MD_JOBS="${MD_JOBS}${MD_JOBS:+,}${JOB}" && PREV_JOB=$JOB
done
[ -n "$MD_JOBS" ] && monitor_slurm_jobs "$MD_JOBS" 4 45
sleep 2
for temp in 273 300 350 400; do
    read_output /tmp/md_${temp}.out 2>/dev/null | grep -E "(Final energy|Equilibration)" 2>/dev/null || true
done
if [ "$USE_OCI_ARTIFACTS" = "true" ] && [ -n "$MD_JOBS" ]; then
    printf "  📦 Artifacting"
    MD_JOBS_COPY="$MD_JOBS"
    for temp in 273 300 350 400; do 
        job_id=$(echo "$MD_JOBS_COPY" | cut -d',' -f1)
        MD_JOBS_COPY=$(echo "$MD_JOBS_COPY" | sed 's/^[^,]*,\?//')
        save_output_to_oci "/tmp/md_${temp}.out" "md-${temp}k" "$job_id" && printf "."
    done
    echo " ✓"
fi

if [ "$ACCOUNTING_ENABLED" = true ] && [ -n "$MD_JOBS" ]; then
    echo -e "\nJobID | State | Elapsed | CPUTime"
    slurm_exec sacct -j "$MD_JOBS" --format=JobID,State,Elapsed,CPUTime -P -n 2>/dev/null | grep -E "^[0-9]+\|" || true
fi

print_demo 4 "Genomics Pipeline (Dependencies)"
JOB_ALIGN=$(slurm_exec sbatch --job-name=alignment --output=/tmp/align.out /tmp/genomics_stage1.sh 2>/dev/null | grep -oP '\d+' || echo "")
JOB_FILTER=$([ -n "$JOB_ALIGN" ] && slurm_exec sbatch --dependency=afterok:$JOB_ALIGN --job-name=filter --output=/tmp/filter.out /tmp/genomics_stage2.sh 2>/dev/null | grep -oP '\d+' || echo "")
JOB_VARIANT=$([ -n "$JOB_FILTER" ] && slurm_exec sbatch --dependency=afterok:$JOB_FILTER --job-name=variants --output=/tmp/variants.out /tmp/genomics_stage3.sh 2>/dev/null | grep -oP '\d+' || echo "")
[ -n "$JOB_ALIGN" ] && [ -n "$JOB_FILTER" ] && [ -n "$JOB_VARIANT" ] && echo "  → $JOB_ALIGN → $JOB_FILTER → $JOB_VARIANT" || echo "  ⚠ Pipeline setup incomplete"
[ -n "$JOB_ALIGN" ] && monitor_slurm_jobs "$JOB_ALIGN,$JOB_FILTER,$JOB_VARIANT" 3 60
sleep 2
read_output /tmp/align.out 2>/dev/null | grep -E "(mapped|coverage)" 2>/dev/null || true
read_output /tmp/filter.out 2>/dev/null | grep -E "(Duplicate|Retained)" 2>/dev/null || true
read_output /tmp/variants.out 2>/dev/null | grep -E "(variants|SNPs|INDELs)" 2>/dev/null || true
if [ "$USE_OCI_ARTIFACTS" = "true" ] && [ -n "$JOB_ALIGN" ]; then
    printf "  📦 Artifacting"
    save_output_to_oci "/tmp/align.out" "genomics-align" "$JOB_ALIGN" && printf "."
    save_output_to_oci "/tmp/filter.out" "genomics-filter" "$JOB_FILTER" && printf "."
    save_output_to_oci "/tmp/variants.out" "genomics-variants" "$JOB_VARIANT" && printf "."
    echo " ✓"
fi

if [ "$ACCOUNTING_ENABLED" = true ] && [ -n "$JOB_ALIGN" ]; then
    echo -e "\nJobID | State | Elapsed | CPUTime"
    slurm_exec sacct -j "$JOB_ALIGN,$JOB_FILTER,$JOB_VARIANT" --format=JobID,State,Elapsed,CPUTime -P -n 2>/dev/null | grep -E "^[0-9]+\|" || true
fi

print_demo 5 "Climate Ensemble"
ENSEMBLE_JOBS=""
for member in 1 2 3; do
    JOB=$(slurm_exec sbatch --job-name=climate_ens${member} --output=/tmp/climate_${member}.out /tmp/ensemble_member.sh $member 2>/dev/null | grep -oP '\d+' || echo "")
    [ -n "$JOB" ] && ENSEMBLE_JOBS="${ENSEMBLE_JOBS}${ENSEMBLE_JOBS:+,}${JOB}"
done
[ -n "$ENSEMBLE_JOBS" ] && echo "  → Jobs: $ENSEMBLE_JOBS" || echo "  ⚠ No jobs submitted"
[ -n "$ENSEMBLE_JOBS" ] && monitor_slurm_jobs "$ENSEMBLE_JOBS" 3 45
sleep 2
for member in 1 2 3; do
    read_output /tmp/climate_${member}.out 2>/dev/null | grep -E "(anomaly|temperature|Sea level)" 2>/dev/null || true
done
if [ "$USE_OCI_ARTIFACTS" = "true" ] && [ -n "$ENSEMBLE_JOBS" ]; then
    printf "  📦 Artifacting"
    for member in 1 2 3; do
        ens_job=$(echo "$ENSEMBLE_JOBS" | cut -d',' -f$member)
        save_output_to_oci "/tmp/climate_${member}.out" "ensemble-${member}" "$ens_job" && printf "."
    done
    echo " ✓"
fi

print_demo 6 "Drug Screening Array"
JOB_SCREEN=$(slurm_exec sbatch --array=1-6%3 --job-name=drug_screen --output=/tmp/screen_%a.out /tmp/drug_screen.sh 2>/dev/null | grep -oP '\d+' || echo "")
if [ -n "$JOB_SCREEN" ]; then
    echo "  → Array job $JOB_SCREEN (6 compounds, max 3 concurrent)"
    release_held_jobs "$JOB_SCREEN" 2>/dev/null || true
    sleep 2
    for i in $(seq 1 60); do
        counts=$(get_job_counts "$JOB_SCREEN")
        read -r running pending <<< "$counts"
        printf "\r\033[K   [t+%ds] Running: %d | Pending: %d | Done: %d/6" "$i" "$running" "$pending" "$((6 - running - pending))"
        [ $((i % 5)) -eq 0 ] && release_held_jobs "$JOB_SCREEN" 2>/dev/null || true
        [ "$running" -eq 0 ] && [ "$pending" -eq 0 ] && break
        sleep 1
    done
    printf "\n"
    for i in {1..6}; do
        output=$(read_output /tmp/screen_${i}.out 2>/dev/null || echo "")
        echo "$output" | grep "HIT:" 2>/dev/null || true
    done
    if [ "$USE_OCI_ARTIFACTS" = "true" ]; then
        printf "  📦 Artifacting"
        for i in {1..6}; do save_output_to_oci "/tmp/screen_${i}.out" "drug-screen-${i}" "${JOB_SCREEN}_${i}" && printf "."; done
        echo " ✓"
    fi
    if [ "$ACCOUNTING_ENABLED" = true ]; then
        echo -e "\nJobID | State | Elapsed | CPUTime"
        slurm_exec sacct -j "$JOB_SCREEN" --format=JobID,State,Elapsed,CPUTime -P -n 2>/dev/null | grep -E "_[0-9]+\|" || true
    fi
else
    echo "  ⚠ Job submission failed, skipping demo"
fi

print_header "Summary"
if slurm_exec squeue -h 2>/dev/null | grep -q .; then
    slurm_exec squeue 2>/dev/null
else
    echo "All jobs completed"
fi

if [ "$USE_OCI_ARTIFACTS" = "true" ] && command -v podman >/dev/null 2>&1; then
    echo "📦 All job outputs artifacted to ${OCI_REGISTRY}/sc25-outputs"
fi

echo ""
echo "Access Slurm: ssh -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST}"
[ "$USE_OCI_ARTIFACTS" = "true" ] && echo "OCI artifacts: podman artifact ls | grep sc25"
