# ArgoCD Applications

App-of-Apps pattern for HPC MCP servers.

## Deploy

**Install ArgoCD:**
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

**Deploy (update repoURL first):**
```bash
# All apps
kubectl apply -f root-app.yaml

# Individual apps
kubectl apply -f applications/slurm-mcp-server.yaml
kubectl apply -f applications/flux-mcp-server.yaml
```

**Access UI:**
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
# https://localhost:8080 (admin / password)
```

## Applications

### Core Infrastructure (Deployed by setup_local_cluster.sh)
**cert-manager** - Certificate management (cert-manager namespace)  
**flux-operator** - Flux Framework operator (operator-system namespace)
  - Source: [Official Flux Operator manifest](https://raw.githubusercontent.com/flux-framework/flux-operator/main/examples/dist/flux-operator.yaml)
  - Operator runs in `operator-system` with label `control-plane: controller-manager`
  - MiniClusters run in separate `flux-operator` namespace with privileged pod security  

**slurm-operator-crds** - Slinky CRDs (default namespace)  
**slurm-operator** - Slinky/Slurm operator (slinky namespace)  

### MCP Servers (Deployed via root-app.yaml)
**root-app.yaml** - Manages all MCP child apps (argocd namespace)  
**shared-resources** - Namespaces & storage (default namespace)  
**slurm-mcp-server** - Slurm MCP server (slurm namespace)  
**flux-mcp-server** - Flux MCP server (flux-operator namespace)  

All use automated sync with prune and self-heal. See [main README](../README.md).

