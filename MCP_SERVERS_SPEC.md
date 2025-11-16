# Unified HPC MCP Server Specification

## Overview

This document provides a comprehensive, language-agnostic specification for a **unified HPC MCP (Model Context Protocol) server** that abstracts multiple workload managers (Slurm, Flux) behind a consistent interface.

**Repository Context**: HPC Containerization with AI Integration (SC25 Demo)

**Design Philosophy**: Based on Anthropic's ["Writing Tools for Agents"](https://www.anthropic.com/engineering/writing-tools-for-agents) best practices:
- Consolidated tools over proliferation (12 tools vs. 20)
- Cluster abstraction hides backend complexity from agents
- Response format optimization for token efficiency
- Meaningful context return (semantic over technical data)
- Higher-level operations that match agent affordances

**Previous Implementation**: 2 separate servers with 20 tools total
**Unified Implementation**: 1 server with 12 tools supporting both backends

**Total Tools**: 12
- 6 core operations (submit, get, list, cancel, queue, output)
- 3 advanced operations (batch, resources, accounting)
- 3 high-level helpers (run_and_wait, validate, analyze)

**Transport Protocol**: HTTP/SSE (streamable-http) via MCP protocol
**Deployment**: Kubernetes pods with service endpoints
**Supported Backends**: Slurm (REST API), Flux (Kubernetes exec)

---

## Cluster Abstraction

The unified server uses a **cluster registry** to abstract backend implementations. Agents work with cluster names, not backend types.

### Cluster Configuration

**clusters.yaml** (or environment-based):
```yaml
clusters:
  - name: "hpc-demo"
    type: "slurm"
    endpoint: "http://slurm-restapi.slurm.svc.cluster.local:6820"
    namespace: "slurm"
    auth:
      user: "slurm"
      jwt_auto_generate: true

  - name: "ai-cluster"
    type: "flux"
    namespace: "flux-operator"
    minicluster: "flux-sample"
    flux_uri: "local:///mnt/flux/view/run/flux/local"
```

### Agent Experience

Agents reference clusters by semantic name:
```python
submit_job(cluster="hpc-demo", script="#!/bin/bash\necho 'Hello'")
submit_job(cluster="ai-cluster", script="#!/bin/bash\necho 'Hello'")
```

Backend type (Slurm vs Flux) is transparent to the agent.

---

## Response Format Standard

All `get_*` and `list_*` operations support a `response_format` parameter for token efficiency:

**Parameter**: `response_format` (string, optional)
- `"concise"` (default): Minimal fields for common use cases (~66% token reduction)
- `"detailed"`: Complete information including technical details

### Example: get_job Response Formats

**Concise (default)**:
```json
{
  "success": true,
  "job": {
    "job_id": "12345",
    "name": "training-job",
    "state": "RUNNING",
    "submitted": "2025-01-14T10:00:00Z",
    "runtime": "00:15:23",
    "exit_code": null
  }
}
```

**Detailed**:
```json
{
  "success": true,
  "job": {
    "job_id": "12345",
    "name": "training-job",
    "state": "RUNNING",
    "user": "slurm",
    "partition": "compute",
    "submitted": "2025-01-14T10:00:00Z",
    "started": "2025-01-14T10:01:15Z",
    "runtime": "00:15:23",
    "time_limit": "01:00:00",
    "exit_code": null,
    "resources": {
      "nodes": 2,
      "tasks": 8,
      "cpus_per_task": 4,
      "memory": "32GB"
    },
    "allocated_nodes": ["node-01", "node-02"],
    "working_directory": "/home/user/jobs",
    "stdout_path": "/home/user/jobs/job-12345.out",
    "stderr_path": "/home/user/jobs/job-12345.err"
  }
}
```

---

## Unified HPC MCP Server

**Purpose**: Single MCP server providing unified interface to multiple HPC workload managers (Slurm, Flux, and potentially PBS/LSF in the future).

**Service Endpoint**: `http://hpc-mcp-server.hpc.svc.cluster.local:5000`

**Configuration Environment Variables**:
- `MCP_PORT`: Server port (default: `5000`)
- `MCP_HOST`: Server host (default: `0.0.0.0`)
- `CLUSTERS_CONFIG`: Path to clusters configuration file (default: `/config/clusters.yaml`)
- `DEFAULT_CLUSTER`: Default cluster if not specified in tool calls

### Health Check

**Endpoint**: `/health`
**Method**: GET
**Returns**:
```json
{
  "status": "healthy",
  "service": "hpc-mcp-server",
  "clusters": ["hpc-demo", "ai-cluster"],
  "backends": {
    "slurm": "connected",
    "flux": "connected"
  }
}
```

---

## Tools

### Core Operations (6 tools)

#### Tool: submit_job

**Description**: Submit a batch job to an HPC cluster

**Parameters**:
- `cluster` (string, required): Cluster name from registry
- `script` (string, required): Job script content including shebang (e.g., `#!/bin/bash`)
- `job_name` (string, optional): Name for the job
- `nodes` (integer, optional): Number of nodes to request
- `tasks_per_node` (integer, optional): Number of tasks per node
- `cpus_per_task` (integer, optional): CPUs per task
- `memory` (string, optional): Memory per node (e.g., `32GB`, `1024MB`)
- `time_limit` (string, optional): Time limit (e.g., `1h`, `30m`, `2:00:00`)
- `partition` (string, optional): Partition/queue to submit to (Slurm only)
- `output_path` (string, optional): Path for stdout output
- `error_path` (string, optional): Path for stderr output
- `working_dir` (string, optional): Working directory for the job

**Returns**: JSON object
```json
{
  "success": true/false,
  "job_id": "string",
  "cluster": "string",
  "backend": "slurm|flux",
  "state": "PENDING|SUBMITTED",
  "error": "string (if failed)"
}
```

**Behavior**:
- Backend auto-selected based on cluster configuration
- Time limit formats normalized across backends
- Defaults to `/tmp` working directory if not specified
- Script must include shebang line

---

#### Tool: get_job

**Description**: Get information about a specific job

**Parameters**:
- `cluster` (string, required): Cluster name
- `job_id` (string, required): Job ID to query
- `response_format` (string, optional): `"concise"` (default) or `"detailed"`

**Returns**: JSON object (format depends on `response_format`)

**Concise**:
```json
{
  "success": true,
  "job": {
    "job_id": "string",
    "name": "string",
    "state": "PENDING|RUNNING|COMPLETED|FAILED|CANCELLED",
    "submitted": "ISO8601 timestamp",
    "runtime": "HH:MM:SS",
    "exit_code": integer or null
  }
}
```

**Detailed**: Adds fields:
```json
{
  "user": "string",
  "partition": "string",
  "started": "ISO8601 timestamp",
  "ended": "ISO8601 timestamp",
  "time_limit": "HH:MM:SS",
  "resources": {
    "nodes": integer,
    "tasks": integer,
    "cpus_per_task": integer,
    "memory": "string"
  },
  "allocated_nodes": ["string"],
  "working_directory": "string",
  "stdout_path": "string",
  "stderr_path": "string"
}
```

**Behavior**:
- Returns normalized job state across backends
- Timestamps in ISO8601 format
- Exit codes: 0 = success, non-zero = failure, null = not completed

---

#### Tool: list_jobs

**Description**: List jobs on a cluster with optional filters

**Parameters**:
- `cluster` (string, required): Cluster name
- `user` (string, optional): Filter by username
- `state` (string, optional): Filter by state (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`)
- `limit` (integer, optional): Maximum number of jobs to return (default: 100)
- `response_format` (string, optional): `"concise"` (default) or `"detailed"`

**Returns**: JSON object
```json
{
  "success": true,
  "jobs": [
    {
      "job_id": "string",
      "name": "string",
      "state": "string",
      "submitted": "ISO8601 timestamp",
      "user": "string"
      // Additional fields if response_format="detailed"
    }
  ],
  "total": integer,
  "filtered": boolean
}
```

**Behavior**:
- Returns most recent jobs first
- Pagination via `limit` parameter
- `total` shows count before limit applied
- Empty filters return all jobs (up to limit)

---

#### Tool: cancel_job

**Description**: Cancel a running or pending job

**Parameters**:
- `cluster` (string, required): Cluster name
- `job_id` (string, required): Job ID to cancel
- `signal` (string, optional): Signal to send (default: `TERM`, options: `TERM`, `KILL`, `INT`)

**Returns**: JSON object
```json
{
  "success": true/false,
  "job_id": "string",
  "state": "CANCELLED|CANCELLING",
  "message": "string",
  "error": "string (if failed)"
}
```

**Behavior**:
- Default signal is graceful termination (SIGTERM)
- `KILL` signal for immediate termination
- Returns error if job already completed

---

#### Tool: get_queue_status

**Description**: Get queue statistics and utilization overview

**Parameters**:
- `cluster` (string, required): Cluster name
- `response_format` (string, optional): `"concise"` (default) or `"detailed"`

**Returns**: JSON object

**Concise**:
```json
{
  "success": true,
  "cluster": "string",
  "total_jobs": integer,
  "running": integer,
  "pending": integer,
  "completed": integer
}
```

**Detailed**: Adds fields:
```json
{
  "failed": integer,
  "cancelled": integer,
  "utilization": {
    "nodes_allocated": integer,
    "nodes_total": integer,
    "cores_allocated": integer,
    "cores_total": integer
  },
  "recent_jobs": [
    {
      "job_id": "string",
      "name": "string",
      "state": "string",
      "runtime": "string"
    }
  ]
}
```

**Behavior**:
- Snapshot of current cluster state
- `recent_jobs` limited to 20 most recent (detailed mode only)
- Provides cluster utilization metrics

---

#### Tool: get_job_output

**Description**: Retrieve stdout and/or stderr from a job

**Parameters**:
- `cluster` (string, required): Cluster name
- `job_id` (string, required): Job ID
- `output_type` (string, optional): `"stdout"` (default), `"stderr"`, or `"both"`
- `tail_lines` (integer, optional): Return only last N lines (default: all)

**Returns**: JSON object
```json
{
  "success": true/false,
  "job_id": "string",
  "stdout": "string (if requested)",
  "stderr": "string (if requested)",
  "truncated": boolean,
  "error": "string (if failed)"
}
```

**Behavior**:
- Reads output files from job working directory
- Uses Kubernetes API to access files from worker pods
- Returns error if job not completed or output unavailable
- `truncated: true` if `tail_lines` applied

---

### Advanced Operations (3 tools)

#### Tool: submit_batch

**Description**: Submit multiple jobs as an array or batch

**Parameters**:
- `cluster` (string, required): Cluster name
- `script` (string, required): Base job script (may include array task variable)
- `array_spec` (string, optional): Array specification for Slurm (e.g., `1-10`, `1-100:2`)
- `commands` (array of strings, optional): List of commands for Flux bulk submission
- `job_name_prefix` (string, optional): Prefix for job names
- `nodes` (integer, optional): Nodes per job
- `tasks_per_node` (integer, optional): Tasks per node per job
- `time_limit` (string, optional): Time limit per job
- `max_concurrent` (integer, optional): Maximum concurrent jobs (Slurm arrays only)
- `response_format` (string, optional): `"concise"` (default) or `"detailed"`

**Returns**: JSON object
```json
{
  "success": true/false,
  "job_ids": ["string"],
  "batch_type": "array|bulk",
  "submitted": integer,
  "failed": integer,
  "errors": [
    {
      "index": integer,
      "command": "string",
      "error": "string"
    }
  ]
}
```

**Behavior**:
- **Slurm**: Uses array jobs with `$SLURM_ARRAY_TASK_ID` variable
  - Single job ID returned for entire array
  - `array_spec` defines task indices
- **Flux**: Bulk submission with individual job tracking
  - Multiple job IDs returned
  - `commands` list defines individual jobs
- Continues on errors, tracks failures in response
- Useful for parameter sweeps and parallel workflows

---

#### Tool: get_resources

**Description**: Get cluster resource availability and configuration

**Parameters**:
- `cluster` (string, required): Cluster name
- `response_format` (string, optional): `"concise"` (default) or `"detailed"`

**Returns**: JSON object

**Concise**:
```json
{
  "success": true,
  "nodes": {
    "total": integer,
    "idle": integer,
    "allocated": integer,
    "down": integer
  },
  "cores": {
    "total": integer,
    "available": integer
  }
}
```

**Detailed**: Adds fields:
```json
{
  "partitions": [
    {
      "name": "string",
      "state": "UP|DOWN",
      "nodes": integer,
      "max_time_limit": "HH:MM:SS",
      "default_memory_per_cpu": "string"
    }
  ],
  "node_details": [
    {
      "name": "string",
      "state": "IDLE|ALLOCATED|MIXED|DOWN",
      "cpus": integer,
      "memory": "string",
      "partitions": ["string"]
    }
  ]
}
```

**Behavior**:
- Provides cluster capacity overview
- Helps agents choose appropriate resource requests
- Partition info (Slurm) or node info (Flux)

---

#### Tool: get_accounting

**Description**: Get historical job accounting and performance data

**Parameters**:
- `cluster` (string, required): Cluster name
- `job_id` (string, optional): Specific job ID to query
- `user` (string, optional): Filter by username
- `start_time` (string, optional): Start of time range (ISO8601)
- `end_time` (string, optional): End of time range (ISO8601)
- `limit` (integer, optional): Maximum records to return (default: 100)
- `response_format` (string, optional): `"concise"` (default) or `"detailed"`

**Returns**: JSON object

**Concise**:
```json
{
  "success": true,
  "jobs": [
    {
      "job_id": "string",
      "name": "string",
      "user": "string",
      "state": "string",
      "exit_code": integer,
      "runtime": "HH:MM:SS",
      "cpu_time": "HH:MM:SS"
    }
  ],
  "total": integer
}
```

**Detailed**: Adds fields:
```json
{
  "memory_used_max": "string",
  "memory_requested": "string",
  "cpu_efficiency": float,
  "wait_time": "HH:MM:SS",
  "nodes_used": ["string"],
  "submit_time": "ISO8601",
  "start_time": "ISO8601",
  "end_time": "ISO8601"
}
```

**Behavior**:
- **Slurm**: Requires slurmdbd (accounting database) configured
- **Flux**: Uses job stats from Flux history
- Useful for resource utilization analysis
- Returns empty list if no matching jobs

---

### High-Level Helpers (3 tools)

#### Tool: run_and_wait

**Description**: Submit a job, wait for completion, and return output (blocking operation)

**Parameters**:
- `cluster` (string, required): Cluster name
- `script` (string, required): Job script content
- `job_name` (string, optional): Name for the job
- `nodes` (integer, optional): Number of nodes
- `tasks_per_node` (integer, optional): Tasks per node
- `time_limit` (string, optional): Time limit
- `timeout_minutes` (integer, optional): Maximum time to wait (default: 60)
- `poll_interval` (integer, optional): Seconds between status checks (default: 10)

**Returns**: JSON object
```json
{
  "success": true/false,
  "job_id": "string",
  "state": "COMPLETED|FAILED|TIMEOUT",
  "exit_code": integer,
  "runtime": "HH:MM:SS",
  "stdout": "string",
  "stderr": "string",
  "error": "string (if failed or timeout)"
}
```

**Behavior**:
- Submits job and polls until completion or timeout
- Returns job output directly upon completion
- Use for short-running jobs or when synchronous execution needed
- Times out after `timeout_minutes`, job continues running
- Reduces multi-step agent interactions (submit → monitor → retrieve)

**Use Cases**:
- Quick validation scripts
- Preprocessing steps in workflows
- Test runs

---

#### Tool: validate_script

**Description**: Validate a job script before submission (pre-flight checks)

**Parameters**:
- `cluster` (string, required): Cluster name
- `script` (string, required): Job script to validate
- `nodes` (integer, optional): Intended node count
- `time_limit` (string, optional): Intended time limit
- `partition` (string, optional): Target partition (Slurm)

**Returns**: JSON object
```json
{
  "success": true/false,
  "valid": boolean,
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "syntax|resources|limits|compatibility",
      "message": "string",
      "line": integer (optional)
    }
  ],
  "recommendations": [
    {
      "field": "string",
      "current": "string",
      "suggested": "string",
      "reason": "string"
    }
  ]
}
```

**Behavior**:
- **Syntax checks**: Shebang present, script is executable
- **Resource validation**:
  - Node count within cluster limits
  - Time limit within partition/queue limits
  - Memory requests feasible
- **Partition availability**: Partition exists and is UP (Slurm)
- **Compatibility**: Detects common errors (missing modules, invalid paths)
- Non-blocking: returns validation results without submission

**Example Issues**:
```json
{
  "issues": [
    {
      "severity": "error",
      "category": "syntax",
      "message": "Script missing shebang line",
      "line": 1
    },
    {
      "severity": "warning",
      "category": "resources",
      "message": "Requested 64 nodes, but cluster only has 32 available"
    }
  ],
  "recommendations": [
    {
      "field": "nodes",
      "current": "64",
      "suggested": "32",
      "reason": "Cluster maximum"
    }
  ]
}
```

---

#### Tool: analyze_job

**Description**: Analyze a job script and predict resource requirements

**Parameters**:
- `cluster` (string, required): Cluster name
- `script` (string, required): Job script to analyze
- `historical_job_id` (string, optional): Reference similar completed job for estimates

**Returns**: JSON object
```json
{
  "success": true,
  "analysis": {
    "estimated_memory": "string",
    "estimated_runtime": "string",
    "recommended_nodes": integer,
    "recommended_tasks": integer,
    "cpu_intensive": boolean,
    "memory_intensive": boolean,
    "io_intensive": boolean
  },
  "recommendations": [
    {
      "parameter": "string",
      "value": "string",
      "confidence": "high|medium|low",
      "reason": "string"
    }
  ],
  "historical_comparison": {
    "similar_jobs": integer,
    "avg_runtime": "string",
    "avg_memory": "string",
    "success_rate": float
  }
}
```

**Behavior**:
- **Script analysis**: Parses script for resource-intensive patterns
  - Large file operations → IO intensive
  - Matrix operations, loops → CPU intensive
  - Large arrays, data structures → Memory intensive
- **Historical comparison**: If `historical_job_id` provided or similar jobs found:
  - Compares to previous runs
  - Provides statistical estimates
- **Recommendations**: Suggests optimal resource allocation
  - Prevents over/under-provisioning
  - Improves queue wait times

**Example Analysis**:
```json
{
  "analysis": {
    "estimated_memory": "16GB",
    "estimated_runtime": "01:30:00",
    "recommended_nodes": 4,
    "recommended_tasks": 16,
    "cpu_intensive": true,
    "memory_intensive": false,
    "io_intensive": false
  },
  "recommendations": [
    {
      "parameter": "nodes",
      "value": "4",
      "confidence": "high",
      "reason": "Script uses MPI with 16 ranks, optimal distribution is 4 nodes × 4 tasks/node"
    },
    {
      "parameter": "time_limit",
      "value": "2h",
      "confidence": "medium",
      "reason": "Similar jobs averaged 1h 30m, adding 25% buffer"
    }
  ]
}
```

**Use Cases**:
- First-time job submissions
- Optimizing resource requests
- Cost/efficiency improvements
- Reducing queue wait times

---

## Implementation Architecture

### Directory Structure

```
unified-hpc-mcp-server/
├── server.py                 # FastMCP server with unified tools
├── cluster_registry.py       # Cluster configuration and discovery
├── backends/
│   ├── base.py              # Abstract base adapter interface
│   ├── slurm_adapter.py     # Slurm backend (REST API client)
│   └── flux_adapter.py      # Flux backend (Kubernetes exec client)
├── formatters/
│   ├── response_formatter.py # Concise/detailed response formatting
│   ├── normalizer.py        # State/timestamp normalization
│   └── schema.py            # Pydantic models for unified responses
├── tools/
│   ├── core.py              # Core 6 tools
│   ├── advanced.py          # Advanced 3 tools
│   └── helpers.py           # High-level 3 tools
├── validators/
│   ├── script_validator.py  # Script syntax and resource validation
│   └── job_analyzer.py      # Resource requirement analysis
├── config/
│   └── clusters.yaml        # Cluster registry configuration
└── tests/
    ├── unit/                # Unit tests per tool
    ├── integration/         # End-to-end workflow tests
    └── fixtures/            # Test data and mock responses
```

### Backend Adapter Interface

All backends implement this abstract interface:

```python
class BackendAdapter(ABC):
    @abstractmethod
    def submit_job(self, params: JobSubmitParams) -> JobSubmitResult:
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> JobDetails:
        pass

    @abstractmethod
    def list_jobs(self, filters: JobFilters) -> List[JobDetails]:
        pass

    @abstractmethod
    def cancel_job(self, job_id: str, signal: str) -> CancelResult:
        pass

    @abstractmethod
    def get_queue_status(self) -> QueueStatus:
        pass

    @abstractmethod
    def get_job_output(self, job_id: str, output_type: str) -> JobOutput:
        pass

    @abstractmethod
    def submit_batch(self, params: BatchSubmitParams) -> BatchSubmitResult:
        pass

    @abstractmethod
    def get_resources(self) -> ResourceInfo:
        pass

    @abstractmethod
    def get_accounting(self, filters: AccountingFilters) -> List[AccountingRecord]:
        pass
```

### Response Normalization

Normalizers convert backend-specific responses to unified schemas:

**State Mapping**:
```python
SLURM_TO_UNIFIED = {
    "PENDING": "PENDING",
    "RUNNING": "RUNNING",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "TIMEOUT": "TIMEOUT"
}

FLUX_TO_UNIFIED = {
    "DEPEND": "PENDING",
    "SCHED": "PENDING",
    "RUN": "RUNNING",
    "INACTIVE": "COMPLETED",  # Check result_code for FAILED
    "CANCELED": "CANCELLED",
    "TIMEOUT": "TIMEOUT"
}
```

**Timestamp Normalization**: All timestamps converted to ISO8601 UTC

**Resource Format Normalization**: Memory, time limits standardized

---

## Tool Consolidation Summary

| Unified Tool | Replaces (Slurm) | Replaces (Flux) | Tool Count Reduction |
|-------------|------------------|-----------------|---------------------|
| submit_job | slurm_submit_job | flux_submit_job | 2 → 1 |
| get_job | slurm_get_job | flux_get_job | 2 → 1 |
| list_jobs | slurm_list_jobs | flux_list_jobs | 2 → 1 |
| cancel_job | slurm_cancel_job | flux_cancel_job | 2 → 1 |
| get_queue_status | slurm_get_queue | flux_get_queue | 2 → 1 |
| get_job_output | slurm_job_output | flux_job_attach | 2 → 1 |
| submit_batch | slurm_submit_array | flux_bulk_submit | 2 → 1 |
| get_resources | slurm_get_nodes + slurm_resource_info | flux_get_resources | 3 → 1 |
| get_accounting | slurm_get_accounting | flux_job_stats | 2 → 1 |
| run_and_wait | *(new)* | *(new)* | 0 → 1 |
| validate_script | *(new)* | *(new)* | 0 → 1 |
| analyze_job | *(new)* | *(new)* | 0 → 1 |
| **TOTAL** | **10 + 2** | **10** | **20 → 12** |

**Net reduction**: 40% fewer tools with expanded functionality

---

## Agent Ergonomics Benefits

### Before (Separate Servers)

```python
# Agent must know backend type
slurm_submit_job(script="...", nodes=4)
flux_submit_job(command="...", nodes=4)

# Different parameter names
slurm_get_job(job_id="12345")
flux_get_job(jobid="ƒAbCd12")  # Different parameter name!

# Multi-step workflow
job_id = slurm_submit_job(...)
while True:
    status = slurm_get_job(job_id)
    if status["state"] == "COMPLETED":
        break
    time.sleep(10)
output = slurm_job_output(job_id)
```

### After (Unified Server)

```python
# Agent uses semantic cluster names
submit_job(cluster="hpc-demo", script="...", nodes=4)
submit_job(cluster="ai-cluster", script="...", nodes=4)

# Consistent parameter names
get_job(cluster="hpc-demo", job_id="12345")
get_job(cluster="ai-cluster", job_id="ƒAbCd12")

# One-step workflow with helper
result = run_and_wait(
    cluster="hpc-demo",
    script="...",
    timeout_minutes=30
)
# Returns output directly!
```

### Token Efficiency Example

**Original** (detailed response from slurm_get_job):
```json
{
  "jobs": [{
    "job_id": "12345",
    "user_id": 1001,
    "user_name": "slurm",
    "account": "default",
    "partition": "compute",
    "name": "test-job",
    "job_state": ["RUNNING"],
    "state_reason": null,
    "derived_exit_code": {"status": ["PENDING"], "return_code": 0},
    "exit_code": {"status": ["PENDING"], "return_code": 0},
    "submit_time": {"number": 1705234567, "set": true},
    "start_time": {"number": 1705234580, "set": true},
    "end_time": {"number": 0, "set": false},
    "time_limit": {"number": 3600, "set": true, "infinite": false},
    "standard_output": "/tmp/slurm-12345.out",
    "standard_error": "/tmp/slurm-12345.err",
    "nodes": "node-[01-02]",
    "node_count": {"number": 2, "set": true, "infinite": false}
    // ... 30+ more fields
  }]
}
```
**~650 tokens**

**Unified (concise)**:
```json
{
  "success": true,
  "job": {
    "job_id": "12345",
    "name": "test-job",
    "state": "RUNNING",
    "submitted": "2025-01-14T10:02:47Z",
    "runtime": "00:15:23",
    "exit_code": null
  }
}
```
**~220 tokens (66% reduction)**

---

## Common Patterns and Behaviors

### Error Handling

All tools follow consistent error handling:

```json
{
  "success": false,
  "error": "Descriptive error message",
  "error_code": "RESOURCE_LIMIT_EXCEEDED",
  "context": {
    "cluster": "hpc-demo",
    "job_id": "12345",
    "backend": "slurm"
  }
}
```

**Error Categories**:
- `VALIDATION_ERROR`: Invalid parameters
- `RESOURCE_LIMIT_EXCEEDED`: Resource requests exceed limits
- `BACKEND_ERROR`: Slurm/Flux backend failure
- `NOT_FOUND`: Job or cluster not found
- `TIMEOUT`: Operation timeout
- `PERMISSION_DENIED`: Authorization failure

### Authentication

**Slurm Backend**:
- JWT token auto-generated from slurm-controller pod
- Tokens cached with 24-hour lifespan
- Auto-refresh on expiration

**Flux Backend**:
- Kubernetes RBAC via service account
- Requires exec permissions on Flux pods

### Kubernetes Integration

- Run as Kubernetes Deployment with Service
- Health checks for readiness/liveness probes
- ConfigMap for cluster configuration
- Secrets for authentication tokens

---

## Deployment Configuration

### Kubernetes Manifests

**manifests/base/deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hpc-mcp-server
  namespace: hpc
  labels:
    app: hpc-mcp-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hpc-mcp-server
  template:
    metadata:
      labels:
        app: hpc-mcp-server
    spec:
      serviceAccountName: hpc-mcp-sa
      containers:
      - name: server
        image: hpc-mcp-server:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 5000
          name: mcp
          protocol: TCP
        env:
        - name: MCP_PORT
          value: "5000"
        - name: MCP_HOST
          value: "0.0.0.0"
        - name: CLUSTERS_CONFIG
          value: "/config/clusters.yaml"
        volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: hpc-clusters-config
```

**manifests/base/service.yaml**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: hpc-mcp-server
  namespace: hpc
  labels:
    app: hpc-mcp-server
spec:
  type: ClusterIP
  selector:
    app: hpc-mcp-server
  ports:
  - port: 5000
    targetPort: 5000
    protocol: TCP
    name: mcp
```

**manifests/base/configmap.yaml**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hpc-clusters-config
  namespace: hpc
data:
  clusters.yaml: |
    clusters:
      - name: "hpc-demo"
        type: "slurm"
        endpoint: "http://slurm-restapi.slurm.svc.cluster.local:6820"
        namespace: "slurm"
        auth:
          user: "slurm"
          jwt_auto_generate: true
      - name: "ai-cluster"
        type: "flux"
        namespace: "flux-operator"
        minicluster: "flux-sample"
```

**manifests/base/rbac.yaml**:
```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: hpc-mcp-sa
  namespace: hpc

---
# ClusterRole for cross-namespace pod exec access
# Required because unified server needs to exec into pods in slurm and flux-operator namespaces
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: hpc-mcp-server
rules:
- apiGroups: [""]
  resources: ["pods", "pods/exec", "pods/log"]
  verbs: ["get", "list", "create"]
- apiGroups: [""]
  resources: ["services"]
  verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: hpc-mcp-server
subjects:
- kind: ServiceAccount
  name: hpc-mcp-sa
  namespace: hpc
roleRef:
  kind: ClusterRole
  name: hpc-mcp-server
  apiGroup: rbac.authorization.k8s.io
```

### RBAC Requirements

The unified server requires **cross-namespace access** to execute commands in backend cluster pods:

**Why ClusterRole is needed:**
- Slurm backend: Exec into pods in `slurm` namespace to generate JWT tokens
- Flux backend: Exec into pods in `flux-operator` namespace to run Flux CLI commands
- Both: Read pod logs for job output retrieval

**Permissions required:**
- `pods/exec`: Execute commands inside Slurm/Flux pods
- `pods`: List and get pod information
- `pods/log`: Read output from completed jobs
- `services`: Discover backend service endpoints

**Security considerations:**
- ClusterRole grants permissions cluster-wide (necessary for multi-namespace access)
- For production: Consider using multiple Role bindings scoped to specific namespaces
- Principle of least privilege: Limit to only required namespaces if possible

**Alternative (Namespace-scoped):**
If deploying in the same namespace as backends, use namespace-scoped Role instead:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: hpc-mcp-role
  namespace: slurm  # Or flux-operator
rules:
- apiGroups: [""]
  resources: ["pods", "pods/exec", "pods/log"]
  verbs: ["get", "list", "create"]
```

---

## Local Cluster Deployment (kind)

### Prerequisites

This section describes deployment to the local `kind` cluster created by `bootstrap/setup_local_cluster.sh`.

**Cluster name**: `hpc-local`

**Installed components:**
- Slurm via Slinky operator (namespace: `slurm`)
- Flux via Flux operator (namespace: `flux-operator`)
- ArgoCD for GitOps (namespace: `argocd`)
- cert-manager (namespace: `cert-manager`)
- MariaDB for Slurm accounting (namespace: `slurm`)

### Setup Local Cluster

```bash
# Create kind cluster with both Slurm and Flux
./bootstrap/setup_local_cluster.sh

# Or install specific operators only:
INSTALL_FLUX=true INSTALL_SLURM=false ./bootstrap/setup_local_cluster.sh
```

### Configuration for Local Cluster

**clusters.yaml for local kind cluster:**
```yaml
clusters:
  - name: "slurm-local"
    type: "slurm"
    endpoint: "http://slurm-restapi.slurm.svc.cluster.local:6820"
    namespace: "slurm"
    auth:
      user: "slurm"
      jwt_auto_generate: true

  - name: "flux-local"
    type: "flux"
    namespace: "flux-operator"
    minicluster: "flux-sample"
    flux_uri: "local:///mnt/flux/view/run/flux/local"
```

**Key differences from production:**
- Cluster names: `slurm-local`, `flux-local` (descriptive of local environment)
- Flux minicluster: Hardcoded to `flux-sample` (default from setup script)
- Single-replica deployment for local testing

### Deployment Steps

**1. Create namespace:**
```bash
kubectl create namespace hpc
kubectl label namespace hpc \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/audit=baseline \
  pod-security.kubernetes.io/warn=baseline
```

**2. Create ConfigMap with local cluster config:**
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: hpc-clusters-config
  namespace: hpc
data:
  clusters.yaml: |
    clusters:
      - name: "slurm-local"
        type: "slurm"
        endpoint: "http://slurm-restapi.slurm.svc.cluster.local:6820"
        namespace: "slurm"
        auth:
          user: "slurm"
          jwt_auto_generate: true
      - name: "flux-local"
        type: "flux"
        namespace: "flux-operator"
        minicluster: "flux-sample"
        flux_uri: "local:///mnt/flux/view/run/flux/local"
EOF
```

**3. Apply RBAC:**
```bash
kubectl apply -f manifests/base/rbac.yaml
```

**4. Build and load image:**
```bash
# Build container image
cd unified-hpc-mcp-server
podman build --platform linux/amd64 -t localhost/hpc-mcp-server:latest -f Containerfile .

# Load into kind cluster
podman save localhost/hpc-mcp-server:latest | \
  kind load image-archive /dev/stdin --name hpc-local
```

**5. Deploy server:**
```bash
kubectl apply -f manifests/base/deployment.yaml
kubectl apply -f manifests/base/service.yaml
```

**6. Verify deployment:**
```bash
# Check pod status
kubectl get pods -n hpc

# Check health endpoint
kubectl port-forward -n hpc svc/hpc-mcp-server 5000:5000
curl http://localhost:5000/health

# Expected output:
# {
#   "status": "healthy",
#   "service": "hpc-mcp-server",
#   "clusters": ["slurm-local", "flux-local"],
#   "backends": {
#     "slurm": "connected",
#     "flux": "connected"
#   }
# }
```

### Local Cluster Access Patterns

**From within cluster:**
```bash
# Service endpoint
http://hpc-mcp-server.hpc.svc.cluster.local:5000
```

**From host (port-forward):**
```bash
kubectl port-forward -n hpc svc/hpc-mcp-server 5000:5000
# Access at http://localhost:5000
```

**From IDE/Agent (Claude Desktop, etc):**
```json
{
  "mcpServers": {
    "hpc": {
      "url": "http://localhost:5000/messages",
      "transport": "streamable-http"
    }
  }
}
```

### Troubleshooting Local Deployment

**Pod not starting:**
```bash
# Check pod logs
kubectl logs -n hpc deployment/hpc-mcp-server

# Check events
kubectl get events -n hpc --sort-by='.lastTimestamp'

# Verify RBAC permissions
kubectl auth can-i get pods --as=system:serviceaccount:hpc:hpc-mcp-sa -n slurm
kubectl auth can-i create pods/exec --as=system:serviceaccount:hpc:hpc-mcp-sa -n slurm
kubectl auth can-i get pods --as=system:serviceaccount:hpc:hpc-mcp-sa -n flux-operator
```

**Backend connection failures:**
```bash
# Test Slurm REST API from within cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://slurm-restapi.slurm.svc.cluster.local:6820/slurm/v0.0.40/diag

# Test Flux access
kubectl exec -it -n flux-operator \
  $(kubectl get pods -n flux-operator -l job-name=flux-sample -o jsonpath='{.items[0].metadata.name}') \
  -c flux-sample -- flux jobs

# Verify namespaces exist
kubectl get namespaces slurm flux-operator
```

**Configuration issues:**
```bash
# Verify ConfigMap is mounted
kubectl exec -n hpc deployment/hpc-mcp-server -- cat /config/clusters.yaml

# Check environment variables
kubectl exec -n hpc deployment/hpc-mcp-server -- env | grep -E '(MCP|CLUSTER)'
```

### Local Testing Workflow

**1. Submit test job to Slurm:**
```bash
# Port-forward MCP server
kubectl port-forward -n hpc svc/hpc-mcp-server 5000:5000 &

# Test via curl (or use MCP client)
curl -X POST http://localhost:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "submit_job",
      "arguments": {
        "cluster": "slurm-local",
        "script": "#!/bin/bash\necho \"Hello from Slurm\"\nhostname",
        "job_name": "test-job"
      }
    },
    "id": 1
  }'
```

**2. Monitor job:**
```bash
# Get job status
curl -X POST http://localhost:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_job",
      "arguments": {
        "cluster": "slurm-local",
        "job_id": "1",
        "response_format": "concise"
      }
    },
    "id": 2
  }'
```

**3. Test Flux backend:**
```bash
curl -X POST http://localhost:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "submit_job",
      "arguments": {
        "cluster": "flux-local",
        "script": "#!/bin/bash\necho \"Hello from Flux\"\nhostname",
        "job_name": "flux-test"
      }
    },
    "id": 3
  }'
```

### Cleanup

```bash
# Delete unified server
kubectl delete namespace hpc

# Delete entire cluster
kind delete cluster --name hpc-local
```

---

## Testing Strategy

### Unit Tests

Test each tool with mocked backends:
- Valid parameters → success responses
- Invalid parameters → validation errors
- Backend failures → error handling
- Response format conversion (concise/detailed)

### Integration Tests

Test with real Slurm/Flux instances:
- End-to-end workflows
- Cross-backend consistency
- Resource limit enforcement
- Authentication flows

### Evaluation Tasks (per Anthropic guidance)

Real-world multi-step scenarios:
1. **ML Training Pipeline**:
   - Validate preprocessing script
   - Analyze resource requirements
   - Submit training job
   - Monitor progress
   - Retrieve results

2. **Parameter Sweep**:
   - Submit batch array with 100 configurations
   - Monitor completion
   - Analyze performance across parameters

3. **Resource Optimization**:
   - Analyze historical job performance
   - Recommend optimal resource allocation
   - Resubmit with optimized parameters

### Load Tests

- Concurrent job submissions (100+ simultaneous)
- High-frequency status polling
- Large batch operations (1000+ jobs)

---

## Future Enhancements

1. **Additional Backends**: PBS, LSF, SGE support via adapter pattern
2. **Multi-Cluster Routing**: Intelligent cluster selection based on workload
3. **Job Templates**: Predefined configurations for common workflows
4. **Streaming Output**: Real-time job output via SSE
5. **Workflow DAGs**: Dependency chains across multiple jobs
6. **Cost Optimization**: Recommend cost-efficient resource allocation
7. **Prometheus Metrics**: Job lifecycle metrics for monitoring
8. **Caching Layer**: Cache frequently-accessed job data
9. **Retry Logic**: Automatic retry for transient failures
10. **Job Priorities**: Priority queue management

---

## Migration Path

### From Existing Servers

For deployments using current Slurm/Flux servers:

1. **Parallel Deployment**: Run unified server alongside existing servers
2. **Gradual Migration**: Update agents to use new cluster-based tools
3. **Backward Compatibility**: Optionally expose legacy tool names as aliases
4. **Validation Period**: Compare responses between old and new servers
5. **Deprecation**: Remove old servers after validation period

### Backward Compatibility (Optional)

```python
# Legacy tool aliases
@mcp.tool()
async def slurm_submit_job(script: str, **kwargs):
    """Deprecated: Use submit_job(cluster='slurm-cluster', ...) instead"""
    return await submit_job(cluster="default-slurm", script=script, **kwargs)
```

---

## Specification Metadata

**Version**: 2.0.0 (Unified)
**Previous Version**: 1.0.0 (Separate Servers)
**Last Updated**: 2025-01-14
**MCP Protocol Version**: 2024-11-05
**Compatibility**: Python 3.12+, Kubernetes 1.24+
**Based On**: [Anthropic's "Writing Tools for Agents"](https://www.anthropic.com/engineering/writing-tools-for-agents)

---

## Appendix: Tool Selection Decision Tree

**For Agents**: How to choose the right tool

```
Need to submit a job?
├─ Quick test/validation (< 5 min)?
│  └─ Use: run_and_wait
├─ First time running this script?
│  ├─ Validate syntax first
│  │  └─ Use: validate_script
│  └─ Estimate resources needed
│     └─ Use: analyze_job → submit_job
├─ Many similar jobs (parameter sweep)?
│  └─ Use: submit_batch
└─ Standard job
   └─ Use: submit_job

Need job information?
├─ Just want to know if it's done?
│  └─ Use: get_job (concise)
├─ Need full details?
│  └─ Use: get_job (detailed)
└─ Need output files?
   └─ Use: get_job_output

Need cluster information?
├─ What's the queue status?
│  └─ Use: get_queue_status
├─ What resources are available?
│  └─ Use: get_resources
└─ How did past jobs perform?
   └─ Use: get_accounting
```
