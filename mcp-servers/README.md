# Unified HPC MCP Server

Single Model Context Protocol (MCP) server that brokers both Slurm REST (`slurmrestd`) and Flux Operator MiniClusters. The runtime and client scaffolding follow the [rdwj/mcp-server-template](https://github.com/rdwj/mcp-server-template) and [rdwj/mcp-client-template](https://github.com/rdwj/mcp-client-template), while Flux MiniCluster specs are validated against the upstream [Flux Operator CRD](https://flux-framework.org/flux-operator/getting_started/custom-resource-definition.html#v1alpha1).

## Security-first Overview

- One hardened container image (`hpc-mcp-server`) with FastMCP HTTP transport.
- Flux MiniCluster CRUD enforces namespace allow-lists, spec validation, and readiness waits without leaking pod details.
- Slurm interactions remain REST-only; Kubernetes RBAC is scoped to `miniclusters` + read-only Pods.
- Network traffic stays on port `5000` with `/health` for probes.

- **Unified Interface:** Single server supporting both Slurm and Flux schedulers
- **Natural Language:** Submit jobs, monitor status, debug failures through conversation
- **Resource Intelligence:** AI-powered recommendations for optimal resource allocation
- **Production Ready:** OpenShift deployment with SSH-based cluster connectivity

## Quick Start

### Prerequisites

- Existing HPC cluster(s) running Slurm and/or Flux
- OpenShift cluster access with `oc` CLI configured
- Network connectivity from OpenShift to your HPC clusters

### Deploy to OpenShift

- Podman or Docker, Python 3.12+, `kind`, `kubectl`, `jq` (for the test script).
- A running demo cluster from `../bootstrap/setup_local_cluster.sh` (deploys Slurm + Flux operators).

# Verify deployment
oc get pods -n hpc-mcp
oc get route -n hpc-mcp
```

### Configure HPC Clusters

```bash
# Build + deploy into kind (uses localhost/hpc-mcp-server:latest by default)
cd mcp-servers
./build_and_deploy.sh

# Verify
kubectl get pods -n hpc-mcp -l app=hpc-mcp-server
kubectl get svc -n hpc-mcp hpc-mcp-server

# Smoke test
./tests/integration_test.sh
```

MCP endpoint: `https://<route-host>/mcp/`

## Integration with LibreChat

```bash
kubectl port-forward -n hpc-mcp svc/hpc-mcp-server 5000:5000
```

- MCP endpoint: `http://localhost:5000/messages`
- Health: `http://localhost:5000/health`

## Tools (10 total)

| Scheduler | Tool | Purpose |
|-----------|------|---------|
| Slurm | `slurm_submit_job` | Secure script-based submission |
| Slurm | `slurm_get_job` | Describe a job |
| Slurm | `slurm_list_jobs` | Filter by state/user |
| Slurm | `slurm_cancel_job` | Cancel pending/running job |
| Slurm | `slurm_queue_summary` | Summarize queue state |
| Flux | `flux_list_miniclusters` | Enumerate MiniClusters in allowed namespaces |
| Flux | `flux_get_minicluster` | Fetch CR + status |
| Flux | `flux_apply_minicluster` | Create/update MiniCluster specs with validation |
| Flux | `flux_scale_minicluster` | Patch size/maxSize |
| Flux | `flux_delete_minicluster` | Secure deletion |

### Job Management
- `submit_job` - Submit jobs with validation
- `submit_job_and_wait` - Submit and block until completion
- `list_jobs` - Query job status with filtering
- `get_job_details` - Detailed job information
- `cancel_job` - Terminate jobs

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Listener host |
| `MCP_PORT` | `5000` | Listener port |
| `MCP_TRANSPORT` | `http` | Transport type |
| `SLURM_REST_URL` | `http://slurm-restapi.slurm.svc.cluster.local:6820` | slurmrestd endpoint |
| `SLURM_NAMESPACE` | `slurm` | Namespace for token generation |
| `SLURM_USER` | `slurm` | REST identity |
| `FLUX_NAMESPACE` | `flux-operator` | Default MiniCluster namespace |
| `FLUX_MINICLUSTER` | `flux-sample` | Default MiniCluster name |
| `ALLOWED_NAMESPACES` | *(empty)* | Comma-separated allow-list for Flux namespaces |

## Example Interactions

Example Cursor/Claude MCP snippet:

```json
{
  "mcpServers": {
    "hpc-mcp": {
      "url": "http://localhost:5000/messages",
      "transport": "sse"
    }
  }
}
```

You can scaffold custom clients using [rdwj/mcp-client-template](https://github.com/rdwj/mcp-client-template) to exercise the same tool surface securely.

## Integration Test

`tests/integration_test.sh` port-forwards the service, checks `/health`, and calls `tools/list`. Requires `jq` and an accessible cluster.

## Development

```bash
# Build
./build.sh --registry localhost --tag latest

# Load into kind manually
podman save localhost/hpc-mcp-server:latest | kind load image-archive /dev/stdin --name hpc-local

# Push to custom registry
./push.sh --registry quay.io/myorg --tag v1.0.0
```

These are minimal deployments for testing MCP functionality, not production HPC.

## Value Proposition

### For Researchers
- Submit jobs in natural language without memorizing commands
- Get AI-assisted debugging of failures
- Optimize resource allocation automatically

- **Pod pending**: `kubectl describe pod -n hpc-mcp -l app=hpc-mcp-server`
- **Flux RBAC**: ensure ServiceAccount `hpc-mcp-sa` has verbs on `flux-framework.org/miniclusters`.
- **Slurm token errors**: `kubectl logs slurm-controller-0 -n slurm -c slurmctld | grep token`
- **Custom namespaces**: set `ALLOWED_NAMESPACES=flux-operator,flux-research` to allow multi-tenancy.
