# HPC Containerization with AI Integration

Kubernetes-native HPC platform combining traditional (Slurm) and modern (Flux) batch schedulers with Model Context Protocol (MCP) servers for seamless LLM integration. Run HPC workloads with AI-assisted workflows in local development environments.

Assisted by: Cursor IDE

## Features

- Slurm (via Slinky) and Flux operator deployments
- Podman rootless containers for HPC
- MCP servers for Slurm/Flux (20 tools total)
- LLM-assisted workflows via IDEs

## Quick Start

```bash
# Setup kind cluster with both operators
./bootstrap/setup_local_cluster.sh

# Build and deploy MCP servers
./mcp-servers/build_and_deploy.sh

# Or use specific operators only:
# INSTALL_FLUX=true INSTALL_SLURM=false ./bootstrap/setup_local_cluster.sh
```

**GitOps (ArgoCD):**
```bash
./bootstrap/setup_local_cluster.sh
cd mcp-servers && ./build.sh
podman save localhost/slurm-mcp-server:latest | kind load image-archive /dev/stdin --name hpc-local
podman save localhost/flux-mcp-server:latest | kind load image-archive /dev/stdin --name hpc-local
kubectl apply -f ../argocd/root-app.yaml
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

**Flux:**
```bash
./bootstrap/demo/demo_flux_jobs.sh
POD=$(kubectl get pods -n flux-operator -l job-name=flux-sample -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $POD -n flux-operator -c flux-sample -- bash -c 'export FLUX_URI=local:///mnt/flux/view/run/flux/local; flux run hostname'
```

**Slurm:**
```bash
./bootstrap/demo/demo_slurm_jobs.sh
kubectl exec -it slurm-controller-0 -n slurm -c slurmctld -- sinfo
```

**MCP Servers:**
```bash
cd mcp-servers && ./build_and_deploy.sh
cd ../tests && ./integration_test.sh
```

## MCP Servers

20 total tools (10 per scheduler) for LLM integration with Slurm/Flux. Kubernetes native with RBAC. [→ Documentation](mcp-servers/README.md)

## Registry

- GitHub Container Registry: `ghcr.io/kush-gupt/*-mcp-server:latest`
- Local: `localhost/*-mcp-server:latest`

```bash
# Build locally
cd mcp-servers
./build.sh --registry localhost --tag latest --builder podman

# Or pull from GHCR
docker pull ghcr.io/kush-gupt/slurm-mcp-server:latest
docker pull ghcr.io/kush-gupt/flux-mcp-server:latest
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


