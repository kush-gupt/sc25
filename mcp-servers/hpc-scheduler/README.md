# HPC Scheduler MCP Server

An MCP (Model Context Protocol) server that provides AI agents with natural language access to HPC batch schedulers (Slurm and Flux). This project demonstrates how conversational AI can dramatically reduce time-to-science by making HPC cluster management more intuitive and accessible.

## The Problem

HPC users spend significant time learning scheduler commands, crafting job scripts, debugging failures, and optimizing resource allocation. The command-line interface, while powerful, has a steep learning curve and requires remembering syntax, flags, and best practices across different scheduler implementations.

## The Solution

This MCP server connects AI agents (like those in LibreChat) directly to your HPC clusters, enabling users to:

- Submit jobs using natural language descriptions
- Get intelligent resource recommendations based on workload analysis
- Debug failed jobs with automated log analysis and suggestions
- Monitor cluster state and queue statistics conversationally
- Optimize resource allocation based on historical data

**Result:** Researchers and scientists can focus on their computational problems instead of scheduler syntax.

## Quick Start

### Prerequisites

- Existing HPC cluster(s) running Slurm and/or Flux
- OpenShift cluster access with `oc` CLI configured
- Network connectivity from OpenShift to your HPC clusters

> **Note:** This project includes test manifests for deploying Flux and Slurm miniclusters if you need them for development/testing (see `manifests/` directory), but assumes most users already have production HPC infrastructure.

### Step 1: Deploy the MCP Server

```bash
# Navigate to the MCP server directory
cd mcp-servers/hpc-scheduler

# Deploy to OpenShift
make deploy PROJECT=hpc-mcp

# Verify deployment
oc get pods -n hpc-mcp
oc get route -n hpc-mcp
```

**Get your MCP server URL:**
```bash
oc get route hpc-scheduler-mcp -n hpc-mcp -o jsonpath='{.spec.host}'
```

Your MCP endpoint: `https://<route-host>/mcp/`

### Step 2: Configure Your HPC Clusters

Point the MCP server to your existing HPC clusters:

```bash
# Configure Slurm clusters
oc set env deployment/hpc-scheduler-mcp \
  SLURM_CLUSTERS="production:hpc-login.example.edu,dev:hpc-dev.example.edu" \
  -n hpc-mcp

# Configure Flux clusters (if applicable)
oc set env deployment/hpc-scheduler-mcp \
  FLUX_CLUSTERS="flux-prod:flux.example.edu" \
  -n hpc-mcp
```

**If your clusters require SSH key authentication:**

```bash
# Create secret with your SSH keys
oc create secret generic hpc-ssh-keys \
  --from-file=id_rsa=/path/to/private/key \
  --from-file=id_rsa.pub=/path/to/public/key \
  -n hpc-mcp

# Mount the secret
oc set volume deployment/hpc-scheduler-mcp \
  --add --type=secret --secret-name=hpc-ssh-keys \
  --mount-path=/app/.ssh \
  -n hpc-mcp
```

### Step 3: Set Up LibreChat

LibreChat provides the conversational interface. Follow the installation guide:

**https://www.librechat.ai/docs/local**

Choose the installation method that fits your environment:
- **Docker/Podman** - Quick setup for evaluation
- **OpenShift** - Production deployment alongside the MCP server
- **Local** - Development and testing

### Step 4: Connect LibreChat to Your MCP Server

Edit your `librechat.yaml`:

```yaml
# librechat.yaml
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
# Docker/Podman deployment
docker-compose restart

# Local installation
npm run restart
```

### Step 5: Create the HPC Assistant Agent

1. **Log into LibreChat** web interface

2. **Create a new Agent:**
   - Navigate to "Agents" → "Create New Agent"
   - **Name:** `HPC Job Management Assistant`
   - **System Prompt:** Copy contents from `agent/system_prompt.md` in this repo
   - **Connected MCP Servers:** Select `hpc-scheduler`
   - **Save**

### Step 6: Experience Natural Language HPC

Start a conversation with your new agent:

```
You: "What clusters are available and what's their current load?"
Agent: [Analyzes cluster state, shows resources, queue depth, utilization]

You: "I need to run a molecular dynamics simulation on 8 nodes with 4 GPUs each for 48 hours"
Agent: [Validates requirements, suggests optimal partition, estimates queue time,
        helps create job script, submits job]

You: "Why did my job 54321 fail?"
Agent: [Reviews job status, analyzes error logs, checks resource usage,
        identifies issue (e.g., memory limit exceeded), suggests solution]

You: "Show me my jobs from the last week and their efficiency"
Agent: [Retrieves historical data, calculates CPU/GPU efficiency,
        identifies optimization opportunities]
```

## Value Proposition

### For Researchers & Scientists
- **Reduced Learning Curve:** No need to memorize scheduler commands or script syntax
- **Faster Debugging:** AI analyzes failures and suggests fixes automatically
- **Better Resource Utilization:** Get intelligent recommendations based on workload patterns
- **Time Saved:** Focus on science, not on battling the scheduler

### For HPC Administrators
- **Better Resource Efficiency:** Users get guidance on right-sizing jobs
- **Reduced Support Tickets:** AI handles common questions and issues
- **Improved User Adoption:** Lower barrier to entry for new HPC users
- **Usage Analytics:** Understand how users interact with the cluster

### For Institutions
- **Faster Time-to-Science:** Researchers spend less time on infrastructure, more on research
- **Broader HPC Access:** Makes HPC accessible to users without deep technical expertise
- **Competitive Advantage:** Differentiate your facility with modern AI-assisted workflows
- **ROI Improvement:** Better cluster utilization and reduced wasted compute cycles

## Architecture

### Components

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

### MCP Tools Available to Agents

The server exposes 15+ tools for comprehensive HPC management:

**Cluster Discovery:**
- `list_clusters` - Enumerate available clusters and their schedulers
- `get_cluster_info` - Detailed cluster configuration and capabilities

**Job Submission & Management:**
- `submit_job` - Submit jobs with validation and optimization hints
- `submit_job_and_wait` - Submit and block until completion (for quick jobs)
- `list_jobs` - Query job status with filtering
- `get_job_details` - Detailed job information
- `cancel_job` - Terminate running or pending jobs

**Monitoring & Analysis:**
- `get_job_output` - Retrieve stdout/stderr logs
- `get_queue_info` - Partition status and availability
- `analyze_job_history` - Historical performance analysis

**Resource Intelligence:**
- `validate_job_script` - Pre-submission script checking
- `analyze_resource_requirements` - Workload-based recommendations
- `get_resource_usage` - Real-time and historical resource consumption

See `src/tools/` for implementation details.

## Configuration

### Cluster Connection

The MCP server connects to your HPC clusters via SSH. Configure using environment variables:

```bash
# Slurm clusters (comma-separated: name:hostname pairs)
SLURM_CLUSTERS="prod:login.hpc.edu,dev:dev-login.hpc.edu"

# Flux clusters
FLUX_CLUSTERS="flux:flux.hpc.edu"

# SSH configuration
SSH_USER="your-username"
SSH_KEY_PATH="/app/.ssh/id_rsa"
```

**Multiple Cluster Support:**
Users can specify which cluster to use when submitting jobs. The agent intelligently selects clusters based on availability and workload requirements.

### Authentication Options

**SSH Keys (Recommended):**
```bash
oc create secret generic hpc-ssh-keys \
  --from-file=id_rsa=~/.ssh/hpc_rsa \
  -n hpc-mcp

oc set volume deployment/hpc-scheduler-mcp \
  --add --type=secret --secret-name=hpc-ssh-keys \
  --mount-path=/app/.ssh \
  -n hpc-mcp
```

**Alternative:** If your clusters support API access, you can modify the adapters to use REST APIs instead of SSH.

## Customizing the Agent

The agent's behavior is defined in `agent/system_prompt.md`. This prompt:

- Defines the agent's role and expertise
- Establishes communication patterns (concise, proactive, educational)
- Provides workflow guidance (validation → submission → monitoring)
- Sets standards for error handling and troubleshooting

**Customization Examples:**

- Add domain-specific guidance (e.g., bioinformatics workflows)
- Adjust verbosity for different user populations
- Include site-specific policies or best practices
- Add specialized analysis for certain job types

After modifying the prompt, update it in your LibreChat agent configuration.

## Development & Testing

### Local Testing (Without OpenShift)

```bash
# Install dependencies
make install

# Run in STDIO mode for local testing
make run-local

# Test with MCP inspector
cmcp ".venv/bin/python -m src.main" tools/list
```

### Testing with Real Clusters

1. Configure cluster credentials in `.env` file
2. Run local server: `make run-local`
3. Use MCP inspector or cmcp to call tools
4. Verify connectivity and tool responses

### Unit Tests

```bash
make test
```

See `tests/` directory for test examples.

## Troubleshooting

### MCP Server Can't Connect to Clusters

**Check connectivity:**
```bash
# Exec into the pod
oc rsh deployment/hpc-scheduler-mcp -n hpc-mcp

# Test SSH connection
ssh -i /app/.ssh/id_rsa user@hpc-login.example.edu

# Test scheduler commands
ssh user@hpc-login.example.edu "squeue --version"
```

**Common issues:**
- SSH keys not properly mounted (check volume mounts)
- Firewall blocking connection (check network policies)
- Wrong hostname or username in configuration
- SSH host key verification (may need to add `StrictHostKeyChecking no` for first connection)

### Agent Not Seeing MCP Tools

1. Check MCP server is running: `oc get pods -n hpc-mcp`
2. Check route is accessible: `curl https://<route>/mcp/health`
3. Verify LibreChat configuration has correct URL
4. Restart LibreChat after configuration changes
5. Check MCP server logs: `oc logs -f deployment/hpc-scheduler-mcp -n hpc-mcp`

### Jobs Failing to Submit

Check MCP server logs for detailed error messages:
```bash
oc logs -f deployment/hpc-scheduler-mcp -n hpc-mcp
```

Common causes:
- Invalid job script syntax
- Resource requirements exceed cluster limits
- Account/partition permissions issues
- Cluster scheduler daemon not running

## Testing Infrastructure (Optional)

For development or proof-of-concept without access to production HPC:

The `manifests/` directory contains OpenShift manifests for deploying test Flux and Slurm miniclusters:

```bash
# Deploy Flux minicluster
oc apply -f manifests/flux-minicluster.yaml -n hpc-mcp

# Deploy Slurm minicluster
oc apply -f manifests/slurm-minimal.yaml -n hpc-mcp
```

These are minimal deployments suitable for testing the MCP server functionality, not for production HPC workloads.

## Roadmap & Future Enhancements

- **Additional Scheduler Support:** PBS Pro, LSF, Grid Engine
- **Advanced Analytics:** Job cost analysis, carbon footprint estimation
- **Workflow Templates:** Common job patterns (array jobs, pipelines, dependencies)
- **Integration with Jupyter:** Submit jobs from notebooks
- **Multi-site Federation:** Manage jobs across multiple institutions
- **Resource Prediction:** ML-based queue time and resource estimation

## Contributing

Contributions welcome! Areas of interest:

- Additional scheduler adapters
- Enhanced job analysis and optimization algorithms
- Integration with other AI platforms (beyond LibreChat)
- Documentation and tutorials
- Testing with diverse HPC configurations

## References

- **MCP Protocol:** https://modelcontextprotocol.io
- **FastMCP Framework:** https://github.com/jlowin/fastmcp
- **LibreChat:** https://www.librechat.ai
- **Slurm Documentation:** https://slurm.schedmd.com
- **Flux Framework:** https://flux-framework.org

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

**Questions or Issues?**

This is a demonstration project proving the value of MCP-enabled AI agents for HPC. We welcome feedback, questions, and contributions as we explore this new paradigm for human-HPC interaction.