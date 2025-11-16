# Unified HPC MCP Server - Tool Specification

## Overview

This document specifies the tools provided by the **unified HPC MCP server** that abstracts multiple workload managers (Slurm, Flux) behind a consistent interface.

**Design Philosophy**: Based on Anthropic's ["Writing Tools for Agents"](https://www.anthropic.com/engineering/writing-tools-for-agents) best practices:
- Consolidated tools over proliferation (12 tools total)
- Cluster abstraction hides backend complexity from agents
- Response format optimization for token efficiency
- Meaningful context return (semantic over technical data)
- Higher-level operations that match agent affordances

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

## Error Handling

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

---

## Tool Selection Decision Tree

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

---

## Specification Metadata

**Version**: 2.0.0 (Unified)
**Last Updated**: 2025-01-14
**MCP Protocol Version**: 2024-11-05
**Compatibility**: Python 3.12+, Kubernetes 1.24+
**Based On**: [Anthropic's "Writing Tools for Agents"](https://www.anthropic.com/engineering/writing-tools-for-agents)
