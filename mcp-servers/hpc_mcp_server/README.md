# HPC MCP Server

Unified Model Context Protocol server that exposes both Slurm REST controls and Flux
Operator MiniCluster lifecycle management via the FastMCP runtime.

## Features

- Single HTTP endpoint (`/messages`) that registers five Slurm tools and five Flux tools.
- Pydantic validation for Flux specs plus namespace allow-lists to prevent privilege
  escalation.
- Automatic Slurm JWT generation when running inside Kubernetes (falls back to `kubectl`
  exec locally).
- Health probe at `/health` for readiness/liveness.

## Local Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m hpc_mcp_server
```

The server listens on `0.0.0.0:5000` by default. Override via `MCP_HOST`/`MCP_PORT`.

## Environment Reference

| Variable | Purpose |
|----------|---------|
| `SLURM_REST_URL` | Base URL for `slurmrestd` |
| `SLURM_NAMESPACE` | Namespace used to exec into `slurm-controller-0` for JWTs |
| `FLUX_NAMESPACE` | Default Flux namespace (must be in the allow-list) |
| `FLUX_MINICLUSTER` | Default MiniCluster name when none is supplied |
| `ALLOWED_NAMESPACES` | Comma-separated list of Flux namespaces |

See `../README.md` for build, deploy, and integration test workflows.

