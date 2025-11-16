FROM registry.redhat.io/ubi9/python-311:latest

WORKDIR /opt/app-root/src

# Install dependencies with pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set environment for HTTP transport
ENV MCP_TRANSPORT=http \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8080 \
    MCP_HTTP_PATH=/mcp/

USER 1001

# Run the application
CMD ["python", "-m", "src.main"]