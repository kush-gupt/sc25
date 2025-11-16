# HPC Job Test Scripts

This directory contains test job scripts for validating the unified HPC MCP server with both Slurm and Flux workload managers.

## Purpose

These scripts are designed to be submitted through the MCP server tools during agent testing. They provide realistic scenarios for testing job submission, monitoring, validation, and output retrieval workflows.

## Directory Structure

```
test_jobs/
├── simple/              # Basic test scripts for core functionality
├── resource_varied/     # Scripts with different resource requirements
├── validation/          # Scripts for testing validation tools
├── batch/              # Array and batch job examples
├── workflows/          # Realistic multi-phase workflows
└── README.md           # This file
```

## Script Categories

### 1. Simple Tests (`simple/`)

Basic scripts for testing core MCP server operations.

| Script | Runtime | Purpose |
|--------|---------|---------|
| `hello_world.sh` | ~5s | Basic job submission and output retrieval |
| `sleep_short.sh` | 30s | Job polling and status monitoring |
| `failure_test.sh` | ~5s | Error handling and non-zero exit codes |
| `stdout_stderr.sh` | ~5s | Output stream separation (stdout vs stderr) |

**Example agent interaction:**
```
User: "Submit hello_world.sh to the hpc-demo cluster"
Agent: Uses run_and_wait or submit_job → get_job → get_job_output
```

### 2. Resource-Varied Tests (`resource_varied/`)

Scripts demonstrating different resource allocation patterns.

| Script | Runtime | Resources | Purpose |
|--------|---------|-----------|---------|
| `single_node.sh` | ~10s | 1 node, 4 tasks | Single-node parallel computation |
| `multi_node.sh` | ~15s | 2-4 nodes, 4 tasks/node | Multi-node distributed work |
| `memory_intensive.sh` | ~20s | 1 node, 4GB+ memory | Memory allocation testing |
| `cpu_intensive.sh` | ~30s | 1 node, 4-8 tasks | CPU-bound computation |

**Example agent interaction:**
```
User: "I need to run memory_intensive.sh. What resources should I request?"
Agent: Uses analyze_job to recommend resources → validate_script → submit_job
```

### 3. Validation Tests (`validation/`)

Scripts with intentional issues for testing validation tools.

| Script | Issue | Expected Result |
|--------|-------|-----------------|
| `missing_shebang.sh` | No `#!/bin/bash` line | ERROR: Missing shebang |
| `excessive_resources.sh` | Impossible resource requests | ERROR/WARNING: Exceeds limits |
| `invalid_partition.sh` | Non-existent partition | ERROR: Partition not found |
| `mixed_valid.sh` | Multiple warnings, but runnable | WARNING: Suboptimal config |

**Example agent interaction:**
```
User: "Can you check if excessive_resources.sh is valid?"
Agent: Uses validate_script with nodes=1000, memory=9999GB
Agent: Returns validation errors before submission attempt
```

### 4. Batch Tests (`batch/`)

Scripts for testing array jobs and bulk submissions.

| File | Type | Purpose |
|------|------|---------|
| `parameter_sweep.sh` | Slurm array | Uses `$SLURM_ARRAY_TASK_ID` for parameter sweeps |
| `batch_commands.txt` | Flux bulk | List of individual commands for parallel execution |

**Example agent interaction:**
```
User: "Run a parameter sweep with 10 different values"
Agent: Uses submit_batch with parameter_sweep.sh and array_spec="1-10"
```

### 5. Workflow Tests (`workflows/`)

Realistic multi-phase workflows for comprehensive testing.

| Script | Runtime | Phases | Purpose |
|--------|---------|--------|---------|
| `ml_training_simulation.sh` | ~2min | 4 phases | ML training with checkpointing |
| `data_preprocessing.sh` | ~90s | 4 stages | Data pipeline workflow |
| `benchmark_suite.sh` | ~2min | 4 benchmarks | System performance testing |

**Example agent interaction:**
```
User: "I have an ML training job. Can you help me run it?"
Agent: Reads ml_training_simulation.sh
Agent: Uses analyze_job → validate_script → submit_job
Agent: Monitors with get_job, retrieves checkpoints with get_job_output
```

## Usage Examples

### Basic Submission

```bash
# Agent receives: "Submit hello_world.sh to hpc-demo"
submit_job(
    cluster="hpc-demo",
    script=<contents of hello_world.sh>,
    job_name="hello-test"
)
```

### With Resource Analysis

```bash
# Agent receives: "Analyze and submit cpu_intensive.sh"
analyze_job(
    cluster="hpc-demo",
    script=<contents of cpu_intensive.sh>
)
# Returns: recommended_nodes=1, recommended_tasks=4

submit_job(
    cluster="hpc-demo",
    script=<contents of cpu_intensive.sh>,
    nodes=1,
    tasks_per_node=4
)
```

### Validation Before Submission

```bash
# Agent receives: "Check if this script is valid before running"
validate_script(
    cluster="hpc-demo",
    script=<contents of script>,
    nodes=64
)
# Returns validation errors/warnings
```

### Batch Submission

```bash
# Agent receives: "Run parameter sweep with values 1-10"
submit_batch(
    cluster="hpc-demo",
    script=<contents of parameter_sweep.sh>,
    array_spec="1-10",
    job_name_prefix="sweep"
)
```

### Quick Test with run_and_wait

```bash
# Agent receives: "Run hello_world.sh and show me the output"
run_and_wait(
    cluster="hpc-demo",
    script=<contents of hello_world.sh>,
    timeout_minutes=5
)
# Returns job output directly
```

## Testing Workflow Recommendations

### Golden Path Testing
Start with these scripts to verify basic functionality:
1. `simple/hello_world.sh` - Basic submit → get → output flow
2. `resource_varied/single_node.sh` - Resource allocation
3. `workflows/ml_training_simulation.sh` - Realistic workflow

### Error Handling Testing
Test validation and error scenarios:
1. `validation/missing_shebang.sh` - Syntax validation
2. `validation/excessive_resources.sh` - Resource limit validation
3. `simple/failure_test.sh` - Non-zero exit code handling

### Advanced Features Testing
Test specialized MCP tools:
1. `batch/parameter_sweep.sh` - Array job submission
2. `resource_varied/memory_intensive.sh` - Resource analysis
3. `workflows/benchmark_suite.sh` - Complex multi-phase jobs

## Expected Agent Behaviors

### Scenario 1: First-Time Job Submission
```
User: "I have a new script to run on the cluster"
Expected Agent Flow:
  1. Read the script file
  2. Call analyze_job to understand resource needs
  3. Call validate_script to check for issues
  4. Call submit_job with recommended parameters
  5. Monitor with get_job
  6. Retrieve output with get_job_output
```

### Scenario 2: Quick Test
```
User: "Run this script and tell me what happens"
Expected Agent Flow:
  1. Read the script file
  2. Call run_and_wait for synchronous execution
  3. Return stdout/stderr directly
```

### Scenario 3: Batch Processing
```
User: "Run this script with 10 different parameters"
Expected Agent Flow:
  1. Read the script file
  2. Call analyze_job to estimate resources per task
  3. Call submit_batch with array_spec="1-10"
  4. Monitor batch progress with list_jobs
```

## Script Execution Notes

### File Permissions
All `.sh` scripts should be executable. If needed:
```bash
chmod +x test_jobs/**/*.sh
```

### Platform Compatibility
- Scripts use standard bash features for maximum compatibility
- Python3 scripts gracefully degrade if Python is unavailable
- No external dependencies required beyond standard Unix tools

### Output Locations
- Most scripts write temporary files to `/tmp`
- Checkpoint and result files are clearly identified in output
- All temporary files use `$$` (process ID) to avoid conflicts

### Runtime Estimates
- **Simple tests**: 5-30 seconds
- **Resource tests**: 10-30 seconds
- **Workflows**: 1-2 minutes
- **Validation tests**: Should fail validation (not run)

## Integration with MCP Tools

### Tool Coverage Matrix

| Script Category | Primary Tools Used |
|----------------|-------------------|
| Simple | `submit_job`, `get_job`, `get_job_output`, `run_and_wait` |
| Resource-varied | `analyze_job`, `get_resources`, `submit_job` |
| Validation | `validate_script` |
| Batch | `submit_batch`, `list_jobs` |
| Workflows | `submit_job`, `get_job`, `get_accounting` |

### Response Format Testing

All `get_*` and `list_*` tools support `response_format`:
- Use **concise** (default) for quick status checks
- Use **detailed** when full job information is needed

Example:
```python
# Quick check
get_job(cluster="hpc-demo", job_id="12345", response_format="concise")

# Full details
get_job(cluster="hpc-demo", job_id="12345", response_format="detailed")
```

## Troubleshooting

### Script Won't Execute
- Check file permissions: `ls -l test_jobs/simple/hello_world.sh`
- Verify shebang line exists: `head -1 test_jobs/simple/hello_world.sh`

### Job Fails Immediately
- Check cluster configuration in MCP server
- Verify cluster name in submission matches configured clusters
- Review job logs with `get_job_output`

### Validation Issues
- For `validation/` scripts, failures are **expected**
- Use these to verify validation tools are working correctly
- Check that appropriate error messages are returned

## Additional Resources

- **MCP Server Tools**: See `UNIFIED_HPC_MCP_TOOLS.md` for complete tool reference
- **Cluster Configuration**: Check MCP server's `clusters.yaml` or environment settings
- **Anthropic Best Practices**: [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

## Quick Start

1. **Start with a simple test:**
   ```
   User to Agent: "Submit test_jobs/simple/hello_world.sh to hpc-demo cluster"
   ```

2. **Try a workflow:**
   ```
   User to Agent: "Analyze and run test_jobs/workflows/ml_training_simulation.sh"
   ```

3. **Test validation:**
   ```
   User to Agent: "Check if test_jobs/validation/excessive_resources.sh is valid with 1000 nodes"
   ```

4. **Experiment with batch jobs:**
   ```
   User to Agent: "Run test_jobs/batch/parameter_sweep.sh as an array job with 10 tasks"
   ```

---

**Last Updated**: 2025-01-16
**MCP Server Version**: 2.0.0 (Unified)
