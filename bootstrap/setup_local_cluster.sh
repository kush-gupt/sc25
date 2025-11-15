#!/bin/bash
set -e

wait_with_logs() {
    local description="$1"
    shift
    local log
    log=$(mktemp)
    if "$@" >"$log" 2>&1; then
        rm -f "$log"
        return 0
    fi
    echo "⚠ ${description} did not complete successfully:"
    cat "$log"
    rm -f "$log"
    return 1
}

CLUSTER_NAME="${CLUSTER_NAME:-hpc-local}"
SLURM_NS="slurm"
SLINKY_NS="slinky"
# Note: Flux Operator runs in operator-system (created by flux-operator.yaml)
# FLUX_NS is for MiniClusters (HPC workloads), not the operator itself
FLUX_NS="flux-operator"

# Configuration flags
INSTALL_SLURM="${INSTALL_SLURM:-true}"
INSTALL_FLUX="${INSTALL_FLUX:-true}"
ENABLE_ACCOUNTING="${ENABLE_ACCOUNTING:-true}"
INSTALL_ARGOCD="${INSTALL_ARGOCD:-true}"

# Login service authentication
# Both SSH keys (root) and SSSD (multi-user) are enabled by default
ENABLE_ROOT_SSH="${ENABLE_ROOT_SSH:-true}"
ENABLE_SSSD="${ENABLE_SSSD:-true}"

# Check prerequisites
command -v docker >/dev/null 2>&1 && RUNTIME="docker" || { 
    command -v podman >/dev/null 2>&1 && { RUNTIME="podman"; export KIND_EXPERIMENTAL_PROVIDER=podman; } || 
    { echo "Error: docker or podman required" >&2; exit 1; }
}
for cmd in kind kubectl helm; do
    command -v $cmd >/dev/null 2>&1 || { echo "Error: $cmd required" >&2; exit 1; }
done

echo "=== Setting up HPC Operators cluster: ${CLUSTER_NAME} ==="
echo "Installing: $([ "$INSTALL_FLUX" = "true" ] && echo -n "Flux ")$([ "$INSTALL_SLURM" = "true" ] && echo -n "Slurm ")$([ "$ENABLE_ACCOUNTING" = "true" ] && echo -n "(with accounting) ")"

# Build authentication description
AUTH_METHODS=""
[ "$ENABLE_ROOT_SSH" = "true" ] && AUTH_METHODS="SSH keys (root)"
[ "$ENABLE_SSSD" = "true" ] && {
    [ -n "$AUTH_METHODS" ] && AUTH_METHODS="${AUTH_METHODS} + SSSD (multi-user)" || AUTH_METHODS="SSSD (multi-user)"
}
echo "Login Authentication: ${AUTH_METHODS}"

# Handle existing cluster
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    read -p "Cluster exists. Delete and recreate? (y/N): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] && kind delete cluster --name "${CLUSTER_NAME}" || kubectl config use-context "kind-${CLUSTER_NAME}"
fi

# Create cluster if needed
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    cat <<EOF | kind create cluster --name "${CLUSTER_NAME}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30022
    hostPort: 2222
  - containerPort: 30080
    hostPort: 8080
EOF
fi

wait_with_logs "all nodes becoming Ready" kubectl wait --for=condition=Ready nodes --all --timeout=120s

# Install ArgoCD first
if [ "$INSTALL_ARGOCD" = "true" ] || [ "$INSTALL_SLURM" = "true" ] || [ "$INSTALL_FLUX" = "true" ]; then
    echo "Installing ArgoCD..."
    
    # Create argocd namespace
    if ! kubectl get namespace argocd >/dev/null 2>&1; then
        kubectl create namespace argocd
    fi
    
    # Install ArgoCD
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml >/dev/null 2>&1
    
    # Wait for all ArgoCD components to be ready
    wait_with_logs "ArgoCD deployments becoming Available" \
        kubectl wait --for=condition=Available --timeout=300s \
        deployment/argocd-server deployment/argocd-repo-server deployment/argocd-applicationset-controller -n argocd || true
    wait_with_logs "argocd-server pods becoming Ready" \
        kubectl wait --for=condition=Ready --timeout=300s \
        pod -l app.kubernetes.io/name=argocd-server -n argocd || true
    wait_with_logs "argocd-repo-server pods becoming Ready" \
        kubectl wait --for=condition=Ready --timeout=300s \
        pod -l app.kubernetes.io/name=argocd-repo-server -n argocd || true
    
    echo "✓ ArgoCD installed"
fi

# Deploy cert-manager via ArgoCD (required by Slurm operator)
if [ "$INSTALL_SLURM" = "true" ]; then
    if ! kubectl get application cert-manager -n argocd >/dev/null 2>&1; then
        echo "Deploying cert-manager..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/cert-manager.yaml" >/dev/null 2>&1
        until [ "$(kubectl get application cert-manager -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do sleep 2; done
        wait_with_logs "cert-manager deployments becoming Available" \
            kubectl wait --for=condition=Available --timeout=300s \
            deployment/cert-manager{,-webhook,-cainjector} -n cert-manager || true
        echo "✓ cert-manager deployed"
    fi
fi

# Deploy Flux Operator via ArgoCD
if [ "$INSTALL_FLUX" = "true" ]; then
    if ! kubectl get application flux-operator -n argocd >/dev/null 2>&1; then
        echo "Deploying Flux Operator..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/flux-operator.yaml" >/dev/null 2>&1
        until [ "$(kubectl get application flux-operator -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do sleep 2; done
        wait_with_logs "Flux operator controller deployment becoming Available" \
            kubectl wait --for=condition=Available --timeout=300s \
            deployment/operator-controller-manager -n operator-system || true
        wait_with_logs "flux MiniCluster CRD establishment" \
            kubectl wait --for condition=established --timeout=60s crd/miniclusters.flux-framework.org || true
        echo "✓ Flux Operator deployed"
    fi
    
    # Create flux-operator namespace for running MiniClusters (separate from operator-system)
    if ! kubectl get namespace "${FLUX_NS}" >/dev/null 2>&1; then
        kubectl create namespace "${FLUX_NS}" >/dev/null 2>&1
        kubectl label --overwrite ns "${FLUX_NS}" \
            pod-security.kubernetes.io/enforce=privileged \
            pod-security.kubernetes.io/audit=privileged \
            pod-security.kubernetes.io/warn=privileged >/dev/null 2>&1
        echo "✓ ${FLUX_NS} namespace created"
    fi
fi

# Deploy Slinky operator via ArgoCD
if [ "$INSTALL_SLURM" = "true" ]; then
    # Deploy CRDs first
    if ! kubectl get application slurm-operator-crds -n argocd >/dev/null 2>&1; then
        echo "Deploying Slurm operator CRDs..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/slurm-operator-crds.yaml" >/dev/null 2>&1
        until [ "$(kubectl get application slurm-operator-crds -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null)" = "Synced" ]; do sleep 2; done
    fi
    
    wait_with_logs "Slurm CRDs establishing" \
        kubectl wait --for condition=established --timeout=120s \
        crd/accountings.slinky.slurm.net \
        crd/controllers.slinky.slurm.net \
        crd/loginsets.slinky.slurm.net \
        crd/nodesets.slinky.slurm.net \
        crd/restapis.slinky.slurm.net \
        crd/tokens.slinky.slurm.net || true
    echo "✓ Slurm CRDs deployed"
    
    # Deploy operator
    if ! kubectl get application slurm-operator -n argocd >/dev/null 2>&1; then
        echo "Deploying Slurm operator..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/slurm-operator.yaml" >/dev/null 2>&1
        until [ "$(kubectl get application slurm-operator -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do sleep 2; done
    fi
    
    wait_with_logs "Slurm operator deployments becoming Available" \
        kubectl wait --for=condition=Available --timeout=300s \
        deployment -l app.kubernetes.io/name=slurm-operator -n "${SLINKY_NS}" || true
    wait_with_logs "Slurm operator pods becoming Ready" \
        kubectl wait --for=condition=Ready --timeout=300s \
        pod -l app.kubernetes.io/name=slurm-operator -n "${SLINKY_NS}" || true
    echo "✓ Slurm operator deployed"

# Create Slurm namespace with privileged security
kubectl get namespace "${SLURM_NS}" >/dev/null 2>&1 || {
    kubectl create namespace "${SLURM_NS}"
    kubectl label --overwrite ns "${SLURM_NS}" \
        pod-security.kubernetes.io/enforce=privileged \
        pod-security.kubernetes.io/audit=privileged \
        pod-security.kubernetes.io/warn=privileged
}

# Deploy MariaDB operator and database for accounting
if [ "$ENABLE_ACCOUNTING" = "true" ]; then
    # Install MariaDB operator CRDs
    if ! helm list -A 2>/dev/null | grep -q "mariadb-operator-crds"; then
        echo "Installing MariaDB operator..."
        helm repo add mariadb-operator https://helm.mariadb.com/mariadb-operator --force-update >/dev/null 2>&1 || true
        helm repo update >/dev/null 2>&1
        helm install mariadb-operator-crds mariadb-operator/mariadb-operator-crds >/dev/null 2>&1
        echo "✓ MariaDB operator CRDs installed"
    fi
    
    # Install MariaDB operator
    if ! kubectl get namespace mariadb >/dev/null 2>&1; then
        kubectl create namespace mariadb >/dev/null 2>&1
    fi
    
    if ! helm list -n mariadb 2>/dev/null | grep -q "mariadb-operator"; then
        helm install mariadb-operator mariadb-operator/mariadb-operator \
          --namespace mariadb --create-namespace --wait --timeout 300s >/dev/null 2>&1
        echo "✓ MariaDB operator installed"
    fi
    
    # Deploy MariaDB instance for Slurm
    if ! kubectl get mariadb mariadb -n "${SLURM_NS}" >/dev/null 2>&1; then
        echo "Deploying MariaDB..."
        cat <<EOF | kubectl apply -f - >/dev/null 2>&1
apiVersion: k8s.mariadb.com/v1alpha1
kind: MariaDB
metadata:
  name: mariadb
  namespace: ${SLURM_NS}
spec:
  rootPasswordSecretKeyRef:
    name: mariadb-root
    key: password
    generate: true
  username: slurm
  database: slurm_acct_db
  passwordSecretKeyRef:
    name: mariadb-password
    key: password
    generate: true
  storage:
    size: 1Gi
  myCnf: |
    [mariadb]
    bind-address=*
    default_storage_engine=InnoDB
    binlog_format=row
    innodb_autoinc_lock_mode=2
    innodb_buffer_pool_size=1024M
    innodb_lock_wait_timeout=900
    innodb_log_file_size=512M
    max_allowed_packet=256M
EOF
        
        wait_with_logs "MariaDB instance becoming Ready" \
            kubectl wait --for=condition=Ready --timeout=300s mariadb/mariadb -n "${SLURM_NS}" || true
        echo "✓ MariaDB deployed"
    fi
fi

# Configure login service authentication
if [ "$ENABLE_ROOT_SSH" = "true" ] && [ ! -f "${HOME}/.ssh/id_ed25519.pub" ]; then
    ssh-keygen -t ed25519 -f "${HOME}/.ssh/id_ed25519" -N "" -C "slurm-login" >/dev/null 2>&1
fi

if [ "$ENABLE_SSSD" = "true" ]; then
    SSSD_CONF_SOURCE="$(dirname "${BASH_SOURCE[0]}")/sssd.conf.example"
    if [ ! -f "${SSSD_CONF_SOURCE}" ]; then
        echo "ERROR: SSSD configuration template not found: ${SSSD_CONF_SOURCE}"
        exit 1
    fi
fi

# Install Slurm cluster
# Check if slurm helm release exists
if ! helm list -n "${SLURM_NS}" --short | grep -q "^slurm$"; then
    echo "Installing Slurm cluster (this may take a few minutes)..."
    
    # Use values file from bootstrap directory
    VALUES_FILE="$(dirname "${BASH_SOURCE[0]}")/slurm-values.yaml"
    HELM_CMD="helm install slurm oci://ghcr.io/slinkyproject/charts/slurm --version=1.0.0-rc1 --namespace=${SLURM_NS} -f ${VALUES_FILE}"
    
    # Override accounting settings if disabled
    if [ "$ENABLE_ACCOUNTING" != "true" ]; then
        HELM_CMD="${HELM_CMD} --set accounting.enabled=false"
    fi
    
    # Add SSH keys for root if enabled
    if [ "$ENABLE_ROOT_SSH" = "true" ]; then
        HELM_CMD="${HELM_CMD} --set-file 'loginsets.slinky.rootSshAuthorizedKeys=${HOME}/.ssh/id_ed25519.pub'"
    fi
    
    # Add SSSD configuration if enabled
    if [ "$ENABLE_SSSD" = "true" ]; then
        HELM_CMD="${HELM_CMD} --set-file 'loginsets.slinky.sssdConf=${SSSD_CONF_SOURCE}'"
    fi
    
    HELM_CMD="${HELM_CMD} --wait --timeout 600s"
    eval "${HELM_CMD}" >/dev/null 2>&1
    
    # Wait for Slurm components
    wait_with_logs "slurmctld pod readiness" \
        kubectl wait --for=condition=Ready pod -l app.kubernetes.io/component=slurmctld -n "${SLURM_NS}" --timeout=600s || echo "⚠ Controller pod not ready yet"
    wait_with_logs "Slurm worker pods readiness" \
        kubectl wait --for=condition=Ready pod -l app.kubernetes.io/component=worker -n "${SLURM_NS}" --timeout=600s || echo "⚠ Worker pods not ready yet"
    wait_with_logs "Slurm login pod readiness" \
        kubectl wait --for=condition=Ready pod -l app.kubernetes.io/component=login -n "${SLURM_NS}" --timeout=600s || echo "⚠ Login pod not ready yet"
    
    # Create default test user if SSSD is enabled
    if [ "$ENABLE_SSSD" = "true" ]; then
        LOGIN_POD=$(kubectl get pods -n "${SLURM_NS}" -l app.kubernetes.io/component=login -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$LOGIN_POD" ]; then
            kubectl exec -n "${SLURM_NS}" "$LOGIN_POD" -- useradd -m -s /bin/bash test >/dev/null 2>&1 || true
            kubectl exec -n "${SLURM_NS}" "$LOGIN_POD" -- sh -c "echo 'test:test' | chpasswd" >/dev/null 2>&1 || true
            
            if [ -f "${HOME}/.ssh/id_ed25519.pub" ]; then
                kubectl cp "${HOME}/.ssh/id_ed25519.pub" "${SLURM_NS}/${LOGIN_POD}:/tmp/test.pub" >/dev/null 2>&1 || true
                kubectl exec -n "${SLURM_NS}" "$LOGIN_POD" -- sh -c "
                    mkdir -p /home/test/.ssh
                    cat /tmp/test.pub > /home/test/.ssh/authorized_keys
                    chown -R test:test /home/test/.ssh
                    chmod 700 /home/test/.ssh
                    chmod 600 /home/test/.ssh/authorized_keys
                    rm -f /tmp/test.pub
                " >/dev/null 2>&1 || true
            fi
            echo "✓ Test user 'test' created"
        fi
    fi
    
    if [ "$ENABLE_ACCOUNTING" = "true" ]; then
        wait_with_logs "Slurm accounting pod readiness" \
            kubectl wait --for=condition=Ready pod slurm-accounting-0 -n "${SLURM_NS}" --timeout=120s || echo "⚠ Accounting pod not ready yet"
        kubectl exec -n "${SLURM_NS}" slurm-controller-0 -c slurmctld -- rm -f /var/spool/slurmctld/slurm_slurm/clustername >/dev/null 2>&1 || true
        kubectl delete pod slurm-controller-0 -n "${SLURM_NS}" >/dev/null 2>&1 || true
        sleep 15
        wait_with_logs "slurm-controller readiness after restart" \
            kubectl wait --for=condition=Ready pod slurm-controller-0 -n "${SLURM_NS}" --timeout=120s || echo "⚠ Controller may still be initializing"
    fi
    
    echo "✓ Slurm cluster deployed"
fi
fi


echo "Deploy MCP Server via GitOps:"
echo "  kubectl apply -f argocd/root-app.yaml"
echo ""
echo "Delete cluster: kind delete cluster --name ${CLUSTER_NAME}"

