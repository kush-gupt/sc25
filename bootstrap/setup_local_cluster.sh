#!/bin/bash
set -e

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

kubectl wait --for=condition=Ready nodes --all --timeout=120s

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
    echo "Waiting for ArgoCD components to be ready..."
    kubectl wait --for=condition=Available --timeout=300s \
        deployment/argocd-server deployment/argocd-repo-server deployment/argocd-applicationset-controller -n argocd 2>/dev/null || true
    
    # Wait for pods to be running
    kubectl wait --for=condition=Ready --timeout=300s \
        pod -l app.kubernetes.io/name=argocd-server -n argocd 2>/dev/null || true
    kubectl wait --for=condition=Ready --timeout=300s \
        pod -l app.kubernetes.io/name=argocd-repo-server -n argocd 2>/dev/null || true
    
    echo "✓ ArgoCD installed successfully"
fi

# Deploy cert-manager via ArgoCD (required by Slurm operator)
if [ "$INSTALL_SLURM" = "true" ]; then
    if ! kubectl get application cert-manager -n argocd >/dev/null 2>&1; then
        echo "Deploying cert-manager via ArgoCD..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/cert-manager.yaml"
        echo -n "Waiting for cert-manager..." && until [ "$(kubectl get application cert-manager -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do echo -n "."; sleep 2; done && echo " ✓"
        
        # Wait for deployments
        kubectl wait --for=condition=Available --timeout=300s \
            deployment/cert-manager{,-webhook,-cainjector} -n cert-manager 2>/dev/null || true
        echo "✓ cert-manager deployed"
    else
        echo "cert-manager ArgoCD application already exists, skipping..."
    fi
fi

# Deploy Flux Operator via ArgoCD
if [ "$INSTALL_FLUX" = "true" ]; then
    if ! kubectl get application flux-operator -n argocd >/dev/null 2>&1; then
        echo "Deploying Flux Operator via ArgoCD..."
        
        # Deploy via ArgoCD (this creates operator-system namespace with correct labels)
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/flux-operator.yaml"
        echo -n "Waiting for Flux Operator..." && until [ "$(kubectl get application flux-operator -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do echo -n "."; sleep 2; done && echo " ✓"
        
        # Wait for Flux Operator deployment
        echo "Waiting for Flux Operator deployment..."
        kubectl wait --for=condition=Available --timeout=300s \
            deployment/operator-controller-manager -n operator-system 2>/dev/null || {
            echo "Note: Flux Operator deployment check timed out, but it may still be starting up"
        }
        
        # Verify CRD is registered
        kubectl wait --for condition=established --timeout=60s crd/miniclusters.flux-framework.org 2>/dev/null || true
        echo "✓ Flux Operator deployed successfully"
    else
        echo "Flux Operator ArgoCD application already exists, skipping..."
    fi
    
    # Create flux-operator namespace for running MiniClusters (separate from operator-system)
    # This namespace needs privileged pod security for running HPC workloads
    if ! kubectl get namespace "${FLUX_NS}" >/dev/null 2>&1; then
        echo "Creating ${FLUX_NS} namespace for MiniClusters..."
        kubectl create namespace "${FLUX_NS}"
        kubectl label --overwrite ns "${FLUX_NS}" \
            pod-security.kubernetes.io/enforce=privileged \
            pod-security.kubernetes.io/audit=privileged \
            pod-security.kubernetes.io/warn=privileged
        echo "✓ ${FLUX_NS} namespace created with privileged pod security"
    fi
fi

# Deploy Slinky operator via ArgoCD
if [ "$INSTALL_SLURM" = "true" ]; then
    # Deploy CRDs first
    if ! kubectl get application slurm-operator-crds -n argocd >/dev/null 2>&1; then
        echo "Deploying Slinky CRDs via ArgoCD..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/slurm-operator-crds.yaml"
        echo -n "Waiting for Slinky CRDs..." && until [ "$(kubectl get application slurm-operator-crds -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null)" = "Synced" ]; do echo -n "."; sleep 2; done && echo " ✓"
    else
        echo "Slinky CRDs ArgoCD application already exists, skipping..."
    fi
    
    echo "Ensuring Slinky CRDs are established..."
    kubectl wait --for condition=established --timeout=120s \
        crd/accountings.slinky.slurm.net \
        crd/controllers.slinky.slurm.net \
        crd/loginsets.slinky.slurm.net \
        crd/nodesets.slinky.slurm.net \
        crd/restapis.slinky.slurm.net \
        crd/tokens.slinky.slurm.net 2>/dev/null || true
    echo "✓ Slinky CRDs ready"
    
    # Deploy operator
    if ! kubectl get application slurm-operator -n argocd >/dev/null 2>&1; then
        echo "Deploying Slinky operator via ArgoCD..."
        kubectl apply -f "$(dirname "${BASH_SOURCE[0]}")/../argocd/applications/slurm-operator.yaml"
        echo -n "Waiting for Slinky operator..." && until [ "$(kubectl get application slurm-operator -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do echo -n "."; sleep 2; done && echo " ✓"
    else
        echo "Slinky operator ArgoCD application already exists, skipping..."
    fi
    
    # Wait for operator to be ready
    echo "Ensuring Slinky operator is ready..."
    kubectl wait --for=condition=Available --timeout=300s \
        deployment -l app.kubernetes.io/name=slurm-operator -n "${SLINKY_NS}" 2>/dev/null || true
    kubectl wait --for=condition=Ready --timeout=300s \
        pod -l app.kubernetes.io/name=slurm-operator -n "${SLINKY_NS}" 2>/dev/null || true
    echo "✓ Slinky operator ready"

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
    echo "Deploying MariaDB operator for Slurm accounting..."
    
    # Install MariaDB operator CRDs
    if ! helm list -A | grep -q "mariadb-operator-crds"; then
        echo "Installing MariaDB operator CRDs..."
        helm repo add mariadb-operator https://helm.mariadb.com/mariadb-operator --force-update 2>/dev/null || true
        helm repo update >/dev/null 2>&1
        helm install mariadb-operator-crds mariadb-operator/mariadb-operator-crds
        echo "✓ MariaDB operator CRDs installed"
    else
        echo "MariaDB operator CRDs already installed"
    fi
    
    # Install MariaDB operator
    if ! kubectl get namespace mariadb >/dev/null 2>&1; then
        kubectl create namespace mariadb
    fi
    
    if ! helm list -n mariadb | grep -q "mariadb-operator"; then
        echo "Installing MariaDB operator..."
        helm install mariadb-operator mariadb-operator/mariadb-operator \
          --namespace mariadb --create-namespace --wait --timeout 300s
        echo "✓ MariaDB operator installed"
    else
        echo "MariaDB operator already installed"
    fi
    
    # Deploy MariaDB instance for Slurm using reference CRD configuration: https://slinky.schedmd.com/projects/slurm-operator/en/release-0.4/installation.html#mariadb-community-edition
    if ! kubectl get mariadb mariadb -n "${SLURM_NS}" >/dev/null 2>&1; then
        echo "Deploying MariaDB instance for Slurm..."
        
        # Create MariaDB custom resource (passwords auto-generated)
        cat <<EOF | kubectl apply -f -
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
        
        # Wait for MariaDB to be ready
        echo "Waiting for MariaDB to be ready..."
        kubectl wait --for=condition=Ready --timeout=300s mariadb/mariadb -n "${SLURM_NS}" 2>/dev/null || true
        
        echo "✓ MariaDB instance deployed with auto-generated passwords"
    else
        echo "MariaDB instance already exists"
    fi
    echo ""
fi

# Configure login service authentication
echo "Configuring login service authentication..."

# SSH key-based authentication for root user
if [ "$ENABLE_ROOT_SSH" = "true" ]; then
    if [ ! -f "${HOME}/.ssh/id_ed25519.pub" ]; then
        echo "  Generating SSH keys for root access..."
        ssh-keygen -t ed25519 -f "${HOME}/.ssh/id_ed25519" -N "" -C "slurm-login"
    fi
    echo "  ✓ SSH key authentication (root user)"
fi

# SSSD-based authentication for multi-user support
if [ "$ENABLE_SSSD" = "true" ]; then
    SSSD_CONF_SOURCE="$(dirname "${BASH_SOURCE[0]}")/sssd.conf.example"
    if [ ! -f "${SSSD_CONF_SOURCE}" ]; then
        echo "  ERROR: SSSD configuration template not found: ${SSSD_CONF_SOURCE}"
        echo "  Please ensure bootstrap/sssd.conf.example exists"
        exit 1
    fi
    echo "  ✓ SSSD multi-user authentication (local users)"
fi

# Install Slurm cluster
# Check if slurm helm release exists
if ! helm list -n "${SLURM_NS}" --short | grep -q "^slurm$"; then
    echo "Installing Slurm cluster (this may take a few minutes)..."
    HELM_CMD="helm install slurm oci://ghcr.io/slinkyproject/charts/slurm --namespace=${SLURM_NS}"
    if [ "$ENABLE_ACCOUNTING" = "true" ]; then
        HELM_CMD="${HELM_CMD} --set accounting.enabled=true"
        # Configure MariaDB connection (using MariaDB operator service)
        HELM_CMD="${HELM_CMD} --set accounting.storageHost=mariadb-primary.${SLURM_NS}.svc.cluster.local"
        HELM_CMD="${HELM_CMD} --set accounting.storagePort=3306"
    fi
    # Configure secure spool directory using /tmp for REST API compatibility
    # Ref: https://github.com/SlinkyProject/slurm-operator
    HELM_CMD="${HELM_CMD} --set controller.extraConfMap.SlurmdSpoolDir=/tmp/slurmd"
    
    # Enable login service with authentication methods
    HELM_CMD="${HELM_CMD} --set 'loginsets.slinky.enabled=true'"
    
    # Add SSH keys for root if enabled
    if [ "$ENABLE_ROOT_SSH" = "true" ]; then
        HELM_CMD="${HELM_CMD} --set-file 'loginsets.slinky.rootSshAuthorizedKeys=${HOME}/.ssh/id_ed25519.pub'"
    fi
    
    # Add SSSD configuration if enabled
    if [ "$ENABLE_SSSD" = "true" ]; then
        HELM_CMD="${HELM_CMD} --set-file 'loginsets.slinky.sssdConf=${SSSD_CONF_SOURCE}'"
    fi
    HELM_CMD="${HELM_CMD} --set 'loginsets.slinky.service.type=NodePort'"
    HELM_CMD="${HELM_CMD} --set 'loginsets.slinky.service.nodePort=30022'"
    
    HELM_CMD="${HELM_CMD} --wait --timeout 600s"
    eval "${HELM_CMD}" 2>&1 | grep -v "^WARNING" || true
    
    echo "Waiting for Slurm components to be ready..."
    
    # Wait for controller
    kubectl wait --for=condition=Ready pod -l app.kubernetes.io/component=slurmctld -n "${SLURM_NS}" --timeout=600s 2>/dev/null || {
        echo "⚠ Warning: Controller pod not ready yet"
    }
    
    # Wait for workers
    kubectl wait --for=condition=Ready pod -l app.kubernetes.io/component=worker -n "${SLURM_NS}" --timeout=600s 2>/dev/null || {
        echo "⚠ Warning: Worker pods not ready yet"
    }
    
    # Wait for login service
    kubectl wait --for=condition=Ready pod -l app.kubernetes.io/component=login -n "${SLURM_NS}" --timeout=600s 2>/dev/null || {
        echo "⚠ Warning: Login pod not ready yet"
    }
    
    # Create default test user if SSSD is enabled
    if [ "$ENABLE_SSSD" = "true" ]; then
        echo "Creating default test user..."
        LOGIN_POD=$(kubectl get pods -n "${SLURM_NS}" -l app.kubernetes.io/component=login -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$LOGIN_POD" ]; then
            
            # Create test user
            kubectl exec -n "${SLURM_NS}" "$LOGIN_POD" -- useradd -m -s /bin/bash test 2>/dev/null || true
            
            # Set default password (test)
            kubectl exec -n "${SLURM_NS}" "$LOGIN_POD" -- sh -c "echo 'test:test' | chpasswd" 2>/dev/null || true
            
            # Add SSH keys if available
            if [ -f "${HOME}/.ssh/id_ed25519.pub" ]; then
                kubectl cp "${HOME}/.ssh/id_ed25519.pub" "${SLURM_NS}/${LOGIN_POD}:/tmp/test.pub" 2>/dev/null || true
                kubectl exec -n "${SLURM_NS}" "$LOGIN_POD" -- sh -c "
                    mkdir -p /home/test/.ssh
                    cat /tmp/test.pub > /home/test/.ssh/authorized_keys
                    chown -R test:test /home/test/.ssh
                    chmod 700 /home/test/.ssh
                    chmod 600 /home/test/.ssh/authorized_keys
                    rm -f /tmp/test.pub
                " 2>/dev/null || true
            fi
            
            echo "✓ Default user 'test' created (password: test)"
        fi
    fi
    
    if [ "$ENABLE_ACCOUNTING" = "true" ]; then
        echo "Configuring accounting components..."
        kubectl wait --for=condition=Ready pod slurm-accounting-0 -n "${SLURM_NS}" --timeout=120s 2>/dev/null || {
            echo "⚠ Warning: slurm-accounting pod not ready yet"
        }
        
        # Clear old cluster state to prevent ID mismatch
        echo "Clearing old cluster state..."
        kubectl exec -n "${SLURM_NS}" slurm-controller-0 -c slurmctld -- rm -f /var/spool/slurmctld/slurm_slurm/clustername 2>/dev/null || true
        
        # Restart controller to apply accounting configuration
        echo "Restarting controller to apply accounting configuration..."
        kubectl delete pod slurm-controller-0 -n "${SLURM_NS}" 2>/dev/null || true
        sleep 15
        kubectl wait --for=condition=Ready pod slurm-controller-0 -n "${SLURM_NS}" --timeout=120s 2>/dev/null || {
            echo "⚠ Controller pod may still be initializing..."
        }
        echo "✓ Accounting configuration applied"
    fi
    
    echo "✓ Slurm cluster installation complete"
else
    echo "Slurm cluster already installed, skipping..."
fi
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "ArgoCD (GitOps):"
echo "  Pods: kubectl get pods -n argocd"
echo "  Applications: kubectl get applications -n argocd"
echo "  Port forward: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "  Get password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo "  UI: https://localhost:8080 (username: admin)"
if [ "$INSTALL_FLUX" = "true" ]; then
    echo ""
    echo "Flux Operator (deployed via ArgoCD):"
    echo "  ArgoCD App: kubectl get application flux-operator -n argocd"
    echo "  Operator pods: kubectl get pods -n operator-system"
    echo "  MiniClusters: kubectl get miniclusters -n ${FLUX_NS}"
    echo "  Verify: ./demo/verify_flux_operator.sh"
    echo "  Demo: ./demo/demo_flux_jobs.sh"
fi
if [ "$INSTALL_SLURM" = "true" ]; then
    echo ""
    echo "Slurm Operator (deployed via ArgoCD):"
    echo "  ArgoCD Apps: kubectl get application slurm-operator-crds,slurm-operator -n argocd"
    echo "  Pods: kubectl get pods -n ${SLURM_NS}"
    echo "  Resources: kubectl get controllers,nodesets,loginsets -n ${SLURM_NS}"
    echo "  Verify: ./demo/verify_slurm_operator.sh"
    echo "  Demo: ./demo/demo_slurm_jobs.sh"
    
    echo ""
    echo "Slurm Login Service:"
    echo "  Authentication: ${AUTH_METHODS}"
    echo ""
    
    if [ "$ENABLE_ROOT_SSH" = "true" ]; then
        echo "  Quick Access (root):"
        echo "    ssh -p 2222 root@localhost sinfo"
        echo ""
    fi
    
    if [ "$ENABLE_SSSD" = "true" ]; then
        echo "  Multi-User Access (SSSD):"
        echo "    Default test user (ready to use):"
        echo "      ssh -p 2222 test@localhost sinfo"
        echo "      Password: test"
        echo ""
    fi
    
    if [ "$ENABLE_ACCOUNTING" = "true" ]; then
        echo ""
        echo "Slurm Accounting:"
        echo "  MariaDB: kubectl get mariadb -n ${SLURM_NS}"
        echo "  Service: mariadb-primary.${SLURM_NS}.svc.cluster.local:3306"
        echo "  Database password: kubectl get secret mariadb-password -n ${SLURM_NS} -o jsonpath='{.data.password}' | base64 -d"
        echo "  Test via login: ssh -p 2222 root@localhost sacct"
        echo "  Test direct: kubectl exec -n ${SLURM_NS} slurm-controller-0 -c slurmctld -- sacct"
        echo "  Check logs: kubectl logs -n ${SLURM_NS} slurm-controller-0 -c slurmdbd"
        echo "  View jobs: ssh -p 2222 root@localhost 'sacct --format=JobID,JobName,State,Elapsed'"
    fi
fi
echo ""
echo "Deploy MCP Servers via GitOps:"
echo "  kubectl apply -f argocd/root-app.yaml"
echo ""
echo "Delete cluster: kind delete cluster --name ${CLUSTER_NAME}"

