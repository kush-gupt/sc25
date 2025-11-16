# Testing Guide

This guide covers how to test the MCP server both locally and on OpenShift.

## Prerequisites

### Local Testing
- Python 3.11+
- cmcp: `pip install cmcp`

### OpenShift Testing
- OpenShift CLI (`oc`)
- MCP Inspector: `npx @modelcontextprotocol/inspector`

## Local Testing (STDIO Transport)

### 1. Install and Run

```bash
# Install dependencies
make install

# Run the server
make run-local
```

### 2. Test with cmcp

In another terminal:

```bash
# List available tools
cmcp ".venv/bin/python -m src.main" tools/list

# Call the echo tool
cmcp ".venv/bin/python -m src.main" tools/call name=echo arguments:='{"message":"Hello MCP"}'

# List prompts
cmcp ".venv/bin/python -m src.main" prompts/list

# Get a specific prompt
cmcp ".venv/bin/python -m src.main" prompts/get name=summarize

# List resources
cmcp ".venv/bin/python -m src.main" resources/list

# Read a resource
cmcp ".venv/bin/python -m src.main" resources/read uri=resource://readme-snippet
```

### 3. Quick Test

```bash
# Run automated local test
make test-local
```

## OpenShift Testing (HTTP Transport)

### 1. Deploy to OpenShift

```bash
# Deploy to default project (mcp-demo)
make deploy

# Or deploy to specific project
make deploy PROJECT=my-project
```

### 2. Get the Server URL

```bash
# Get the route
oc get route mcp-server -o jsonpath='{.spec.host}'
```

### 3. Test with MCP Inspector

```bash
# Launch MCP Inspector
npx @modelcontextprotocol/inspector https://<route-url>/mcp/
```

The Inspector provides a web UI to:
- Browse available tools, prompts, and resources
- Execute tools interactively
- Test prompt generation
- View server capabilities

### 4. Test with curl (Advanced)

```bash
# Get server info (streamable-http endpoint)
curl -X POST https://<route-url>/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"1.0.0","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}'
```

## Unit Tests

Run the pytest suite:

```bash
# Run all tests
make test

# Run with verbose output
.venv/bin/pytest tests/ -v

# Run specific test file
.venv/bin/pytest tests/test_loaders.py -v

# Run with coverage
.venv/bin/pytest tests/ --cov=src --cov-report=html
```

## Troubleshooting

### Local Issues

1. **cmcp not found**
   ```bash
   pip install cmcp
   ```

2. **Module not found errors**
   ```bash
   # Ensure virtual environment is activated
   source .venv/bin/activate
   ```

3. **Permission denied**
   ```bash
   chmod +x deploy.sh
   ```

### OpenShift Issues

1. **Not logged in**
   ```bash
   oc login <cluster-url>
   ```

2. **Build fails**
   ```bash
   # Check build logs
   oc logs -f bc/mcp-server
   ```

3. **Pod not running**
   ```bash
   # Check pod status
   oc get pods
   
   # Check pod logs
   oc logs <pod-name>
   ```

4. **Route not accessible**
   ```bash
   # Verify route exists
   oc get route mcp-server
   
   # Check service
   oc get svc mcp-server
   ```

## Environment Variables

### Local Development
```bash
export MCP_TRANSPORT=stdio
export MCP_HOT_RELOAD=1
```

### OpenShift Deployment
The following are set automatically in the container:
- `MCP_TRANSPORT=http`
- `MCP_HTTP_HOST=0.0.0.0`
- `MCP_HTTP_PORT=8080`
- `MCP_HTTP_PATH=/mcp/`

## Tips

1. **Hot Reload**: Local development includes hot-reload for tools and prompts
2. **Verbose Mode**: Use `-v` flag with cmcp for detailed request/response
3. **Multiple Projects**: Deploy to different OpenShift projects for testing
4. **Clean Up**: Use `make clean PROJECT=<name>` to remove deployments