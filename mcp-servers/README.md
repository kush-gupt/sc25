# MCP Servers for HPC Workload Managers

Model Context Protocol servers for Slurm and Flux, enabling LLM integration with HPC schedulers.

## Overview

Two MCP servers that run as pods in Kubernetes:
- **Slurm MCP**: Interacts via REST API (slurmrestd)
- **Flux MCP**: Interacts via Kubernetes API

## Prerequisites

```bash
# Setup local cluster with Slurm/Flux
../bootstrap/setup_local_cluster.sh
```

Requirements: Podman, Python 3.12+

## Quick Start

```bash
# Build and deploy
./build_and_deploy.sh

# Verify
kubectl get pods -n slurm -l app=slurm-mcp-server
kubectl get pods -n flux-operator -l app=flux-mcp-server

# Test
cd ../tests && ./integration_test.sh
```

## Access

**Port-forward for external access:**
```bash
kubectl port-forward -n slurm svc/slurm-mcp-server 5000:5000
kubectl port-forward -n flux-operator svc/flux-mcp-server 5001:5001
```

**Endpoints:**
- Slurm: `http://localhost:5000/messages`
- Flux: `http://localhost:5001/messages`
- Health: `http://localhost:{5000,5001}/health`

## Available Tools (20 total)

**Slurm (10):** submit_job, get_job, list_jobs, cancel_job, get_queue, get_nodes, submit_array, get_accounting, job_output, resource_info

**Flux (10):** submit_job, get_job, list_jobs, cancel_job, get_queue, get_resources, job_attach, job_stats, submit_with_deps, bulk_submit

## Configuration

**Slurm Environment:**
- `SLURM_REST_URL`: http://slurm-restapi.slurm.svc.cluster.local:6820
- `SLURM_USER`: slurm (auto-generates JWT tokens)
- `SLURM_NAMESPACE`: slurm

**Flux Environment:**
- `FLUX_URI`: local:///mnt/flux/view/run/flux/local
- `FLUX_NAMESPACE`: flux-operator
- `FLUX_MINICLUSTER`: flux-sample

## Client Configuration

### Claude Desktop / Cursor

Add to MCP config (`claude_desktop_config.json` or Cursor settings):

```json
{
  "mcpServers": {
    "slurm-hpc": {
      "url": "http://localhost:5000/messages",
      "transport": "sse"
    },
    "flux-hpc": {
      "url": "http://localhost:5001/messages",
      "transport": "sse"
    }
  }
}
```

Requires port-forwarding (see Access section above).

## Development

**Build images:**
```bash
./build.sh                    # Both servers
./build.sh --slurm-only       # Slurm only
./build.sh --flux-only        # Flux only
```

**Load into kind:**
```bash
podman save localhost/slurm-mcp-server:latest | kind load image-archive /dev/stdin --name hpc-local
podman save localhost/flux-mcp-server:latest | kind load image-archive /dev/stdin --name hpc-local
```

**Push to registry:**
```bash
./push.sh --registry quay.io/myorg --tag v1.0.0
```

## Troubleshooting

**Connection errors:** Check services exist with `kubectl get svc -n {slurm,flux-operator}`

**Auth errors:** JWT tokens auto-generate from slurm-controller-0 pod

**RBAC errors:** Check with `kubectl get sa,role,rolebinding -n {slurm,flux-operator}`

**Logs:** `kubectl logs -n {namespace} -l app={slurm,flux}-mcp-server`

## References

[MCP](https://modelcontextprotocol.io/) • [Slurm REST API](https://slurm.schedmd.com/rest.html) • [Flux](https://flux-framework.org/) • [Slinky](https://slinky.schedmd.com/) • [Flux Operator](https://github.com/flux-framework/flux-operator/)
