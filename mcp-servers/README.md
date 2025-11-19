# HPC Scheduler MCP Server

Model Context Protocol server providing AI agents with natural language access to HPC batch schedulers (Slurm and Flux). This server enables conversational interaction with high-performance computing clusters, dramatically reducing time-to-science.

## Overview

This MCP server connects AI agents (like LibreChat) to your existing HPC infrastructure, providing:

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

```bash
cd hpc-scheduler

# Deploy the MCP server
make deploy PROJECT=hpc-mcp

# Verify deployment
oc get pods -n hpc-mcp
oc get route -n hpc-mcp
```

### Configure HPC Clusters

```bash
# Point to your existing clusters
oc set env deployment/hpc-scheduler-mcp \
  SLURM_CLUSTERS="prod:hpc-login.example.edu,dev:hpc-dev.example.edu" \
  FLUX_CLUSTERS="flux:flux.example.edu" \
  -n hpc-mcp

# Add SSH credentials (if required)
oc create secret generic hpc-ssh-keys \
  --from-file=id_rsa=~/.ssh/hpc_rsa \
  -n hpc-mcp

oc set volume deployment/hpc-scheduler-mcp \
  --add --type=secret --secret-name=hpc-ssh-keys \
  --mount-path=/app/.ssh \
  -n hpc-mcp
```

### Get MCP Server URL

```bash
oc get route hpc-scheduler-mcp -n hpc-mcp -o jsonpath='{.spec.host}'
```

MCP endpoint: `https://<route-host>/mcp/`

## Integration with LibreChat

### Install LibreChat

Follow the installation guide at: https://www.librechat.ai/docs/local

Choose your deployment method:
- **Docker/Podman** - Quick setup
- **OpenShift** - Production deployment
- **Local** - Development

### Configure LibreChat

Edit `librechat.yaml`:

```yaml
endpoints:
  mcp:
    servers:
      - name: "hpc-scheduler"
        url: "https://<your-mcp-route-host>/mcp/"
        transport: "http"
        description: "HPC Job Scheduling (Slurm & Flux)"
```

Restart LibreChat:
```bash
docker-compose restart  # or npm run restart
```

### Create HPC Assistant Agent

1. Log into LibreChat
2. Navigate to "Agents" → "Create New Agent"
3. **Name:** `HPC Job Management Assistant`
4. **System Prompt:** Copy contents from `hpc-scheduler/agent/system_prompt.md`
5. **Connected MCP Servers:** Select `hpc-scheduler`
6. Save

## Available Tools

The MCP server exposes 15+ tools for comprehensive HPC management:

### Cluster Discovery
- `list_clusters` - Enumerate available clusters and schedulers
- `get_cluster_info` - Detailed cluster configuration

### Job Management
- `submit_job` - Submit jobs with validation
- `submit_job_and_wait` - Submit and block until completion
- `list_jobs` - Query job status with filtering
- `get_job_details` - Detailed job information
- `cancel_job` - Terminate jobs

### Monitoring & Analysis
- `get_job_output` - Retrieve stdout/stderr logs
- `get_queue_info` - Partition status and availability
- `analyze_job_history` - Historical performance analysis

### Resource Intelligence
- `validate_job_script` - Pre-submission validation
- `analyze_resource_requirements` - Workload-based recommendations
- `get_resource_usage` - Resource consumption metrics

## Example Interactions

```
User: "What clusters are available?"
Agent: [Lists Slurm and Flux clusters with current status]

User: "Submit a job to run my simulation on 8 nodes with 4 GPUs each"
Agent: [Validates requirements, creates job script, submits, returns job ID]

User: "Why did job 12345 fail?"
Agent: [Analyzes logs, identifies issue, suggests solution]

User: "Show efficiency of my jobs this week"
Agent: [Retrieves historical data, calculates metrics, recommends optimizations]
```

## Architecture

```
┌─────────────────┐
│   LibreChat     │  ← Conversational Interface
│   (AI Agent)    │
└────────┬────────┘
         │ MCP Protocol (HTTP)
         │
┌────────▼────────────────────────┐
│  HPC Scheduler MCP Server       │
│  (OpenShift Deployment)         │
│                                 │
│  ┌─────────────────────────┐   │
│  │  Unified Tool Interface │   │
│  └───────┬─────────────────┘   │
│          │                      │
│  ┌───────▼──────┐  ┌──────────┐│
│  │Slurm Adapter │  │Flux      ││
│  │              │  │Adapter   ││
│  └──────────────┘  └──────────┘│
└─────────┬───────────┬───────────┘
          │           │
          │ SSH/CLI   │ SSH/CLI
          │           │
┌─────────▼───────────▼───────────┐
│   Your HPC Clusters             │
│   (Existing Infrastructure)     │
└─────────────────────────────────┘
```

## Development

### Local Testing

```bash
cd hpc-scheduler

# Install dependencies
make install

# Run in STDIO mode
make run-local

# Test with cmcp
make test-local

# Run tests
make test
```

### Working with Code

See `hpc-scheduler/` directory for:
- `README.md` - Detailed documentation
- `ARCHITECTURE.md` - System design
- `TESTING.md` - Testing strategies
- `docs/TOOLS_GUIDE.md` - Creating tools
- `agent/system_prompt.md` - Agent behavior definition

## Troubleshooting

### MCP Server Not Connecting to Clusters

```bash
# Check connectivity from pod
oc rsh deployment/hpc-scheduler-mcp -n hpc-mcp
ssh -i /app/.ssh/id_rsa user@hpc-login.example.edu "squeue --version"
```

Common issues:
- SSH keys not mounted (check volume mounts)
- Firewall blocking connection
- Incorrect hostname/username
- SSH host key verification

### Agent Not Seeing Tools

1. Verify MCP server running: `oc get pods -n hpc-mcp`
2. Check route accessible: `curl https://<route>/mcp/health`
3. Verify LibreChat config has correct URL
4. Restart LibreChat
5. Check logs: `oc logs -f deployment/hpc-scheduler-mcp -n hpc-mcp`

## Testing Infrastructure (Optional)

For development without production HPC access:

```bash
# Deploy test Slurm minicluster
oc apply -f hpc-scheduler/manifests/slurm-minimal.yaml -n hpc-mcp

# Deploy test Flux minicluster
oc apply -f hpc-scheduler/manifests/flux-minicluster.yaml -n hpc-mcp
```

These are minimal deployments for testing MCP functionality, not production HPC.

## Value Proposition

### For Researchers
- Submit jobs in natural language without memorizing commands
- Get AI-assisted debugging of failures
- Optimize resource allocation automatically

### For HPC Administrators
- Reduce support tickets through self-service AI assistance
- Improve cluster efficiency with intelligent resource recommendations
- Lower barrier to entry for new users

### For Institutions
- Faster time-to-science
- Better ROI on HPC investments
- Competitive advantage through modern AI-assisted workflows

## Contributing

Contributions welcome! Areas of interest:
- Additional scheduler support (PBS, LSF, Grid Engine)
- Enhanced analytics and optimization
- Integration with other AI platforms
- Documentation and tutorials

## References

- **MCP Protocol:** https://modelcontextprotocol.io
- **FastMCP Framework:** https://github.com/jlowin/fastmcp
- **LibreChat:** https://www.librechat.ai
- **Slurm:** https://slurm.schedmd.com
- **Flux:** https://flux-framework.org

## License

MIT License - See LICENSE file for details.
