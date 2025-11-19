# MCP and Agent for HPC Job Handling

Kubernetes-native HPC platform combining traditional (Slurm) and modern (Flux) batch schedulers with a unified Model Context Protocol (MCP) server.

## Features

- Bootstrap script that brings up Slurm (Slinky) and Flux operators with kind + Podman.
- Unified MCP server (`hpc-mcp-server`) exposing 5 Slurm and 5 Flux MiniCluster tools.
- Podman-first container tooling end to end (CI/CD, local dev, GitOps).

## Quick Start

```bash
# 1. Create / refresh the local cluster with both operators
./bootstrap/setup_local_cluster.sh

# 2. Build + deploy the MCP server
cd mcp-servers
./build.sh --registry localhost --tag latest --builder podman
./build_and_deploy.sh

# 3. Smoke test the MCP server once it is running
./tests/integration_test.sh
```

**GitOps (ArgoCD):**

```bash
./bootstrap/setup_local_cluster.sh
cd mcp-servers && ./build.sh --registry localhost --tag latest --builder podman
podman save localhost/hpc-mcp-server:latest | kind load image-archive /dev/stdin --name hpc-local
kubectl apply -f ../argocd/root-app.yaml
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

## MCP Server

Unified FastMCP runtime that exposes Slurm job controls and Flux MiniCluster lifecycle tooling with shared security controls. [→ Documentation](mcp-servers/README.md)

## Registry

- GitHub Container Registry: `ghcr.io/kush-gupt/hpc-mcp-server:latest`
- Local Podman: `localhost/hpc-mcp-server:latest`

```bash
# Build locally
cd mcp-servers
./build.sh --registry localhost --tag latest --builder podman

# Or pull/push unified image
podman pull ghcr.io/kush-gupt/hpc-mcp-server:latest
```

## License

MIT License - see [LICENSE](LICENSE)

## References & Acknowledgments

This project leverages several AMAZING open-source technologies:

- [Podman](https://docs.podman.io/)
- [Slurm Workload Manager](https://www.schedmd.com/slurm.html) - Traditional HPC scheduler
- [Flux Framework](https://flux-framework.org/) - Next-generation HPC scheduler
- [Slinky](https://slinky.schedmd.com/) - Kubernetes operator for Slurm
- [Flux Operator](https://github.com/flux-framework/flux-operator) - Kubernetes operator for Flux
- [Model Context Protocol](https://modelcontextprotocol.io/) - LLM integration standard
- [ArgoCD](https://argo-cd.readthedocs.io/) - GitOps continuous delivery
- [kind](https://kind.sigs.k8s.io/) - Kubernetes in Docker
