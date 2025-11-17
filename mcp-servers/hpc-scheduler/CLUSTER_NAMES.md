# HPC Cluster Names Reference

This document lists the correct cluster names to use when testing the HPC Scheduler MCP Server.

## Available Clusters

The MCP server is configured with the following cluster names:

### 1. Flux Framework Cluster
- **Cluster Name**: `flux-local`
- **Type**: Flux
- **Namespace**: `flux-sample` (OpenShift)
- **MiniCluster**: `flux-sample`
- **Status**: ✅ Working (7/12 tools functional)

### 2. Slurm Cluster
- **Cluster Name**: `slurm-local`
- **Type**: Slurm
- **Endpoint**: `http://slurm-restapi.slurm.svc.cluster.local:6820`
- **Namespace**: `slurm` (OpenShift)
- **Status**: ✅ Authentication working, read operations functional
- **Note**: Job submission requires shared storage configuration

## Usage Examples

### Using the MCP Server Tools

```bash
# List jobs on Flux cluster
mcp_tool list_jobs --cluster flux-local

# List jobs on Slurm cluster
mcp_tool list_jobs --cluster slurm-local

# Submit a job to Flux (note the time format!)
mcp_tool submit_job --cluster flux-local --script "#!/bin/bash\necho 'Hello from Flux'" --time-limit "10m"

# Submit a job to Slurm (can use HH:MM:SS or FSD)
mcp_tool submit_job --cluster slurm-local --script "#!/bin/bash\necho 'Hello from Slurm'" --time-limit "1:00:00"

# Get job details from Slurm
mcp_tool get_job --cluster slurm-local --job-id 12345
```

### Important: Time Limit Formats

**Flux clusters (`flux-local`)** use Flux Standard Duration (FSD):
- ✅ Correct: `"10m"`, `"1h"`, `"30s"`, `"1.5h"`
- ❌ Wrong: `"00:10:00"`, `"1:00:00"` (will fail with "invalid Flux standard duration" error)

**Slurm clusters (`slurm-local`)** accept both formats:
- ✅ FSD format: `"10m"`, `"1h"`, `"30s"`
- ✅ HH:MM:SS format: `"1:00:00"`, `"00:30:00"`

**Best Practice**: Use FSD format (`"10m"`, `"1h"`) for all clusters since it works everywhere.

### Using with Test Files

When creating test files or batch job scripts, always use the correct cluster names:

```bash
# Correct ✅
cluster: flux-local
cluster: slurm-local

# Incorrect ❌ (will result in error)
cluster: flux-cluster
cluster: slurm-cluster
cluster: flux
cluster: slurm
```

## Error Messages

If you use an incorrect cluster name, you'll see:

```
Cluster 'flux-cluster' not found. Available clusters: slurm-local, flux-local
```

## Configuration

The cluster names are defined in:
- **Environment Variables**: See `openshift.yaml` for deployment configuration
- **Default Configuration**: `src/cluster_registry.py` (lines 57-113)
- **Custom Configuration**: Can be overridden with `config/clusters.yaml` (if created)

## Functional Status

### Flux Cluster (`flux-local`)
Working tools (7/12):
- ✅ **submit_job** - Submit a single job to Flux
- ✅ **list_jobs** - List all jobs in the cluster
- ✅ **get_job** - Get detailed information about a specific job
- ✅ **get_job_output** - Retrieve stdout/stderr from a job
- ✅ **cancel_job** - Cancel a running or pending job
- ✅ **run_and_wait** - Submit a job and wait for completion
- ✅ **analyze_job** - Analyze a job script and provide resource recommendations

Not implemented for Flux (5/12):
- ❌ **get_queue_status** - Not applicable to Flux architecture
- ❌ **get_resources** - Not yet implemented
- ❌ **validate_script** - Not yet implemented (depends on get_resources)
- ❌ **submit_batch** - **Use submit_job multiple times instead**
- ❌ **get_accounting** - Not applicable to Flux architecture

> **Important for Batch Jobs**: The `submit_batch` tool is not implemented for Flux.
> To submit multiple jobs to Flux, call `submit_job` multiple times with different scripts.

### Slurm Cluster (`slurm-local`)
- ✅ Authentication (JWT HS256)
- ✅ list_jobs
- ✅ get_job
- ⚠️  submit_job (requires shared storage for REST API)
- ✅ Other read operations

## Testing

All test files in `tests/tools/` use the correct cluster names. For example:

```python
# From tests/tools/test_get_job.py
result = await get_job_fn(cluster="slurm-local", job_id="12345")

# From tests/tools/test_submit_batch.py
result = await submit_batch_fn(cluster="flux-local", ...)
```

## Need Help?

If you're unsure which cluster to use:
1. Use `flux-local` for general HPC job testing (more tools available)
2. Use `slurm-local` for Slurm-specific features or testing
3. The MCP server will return helpful error messages if cluster names are incorrect
