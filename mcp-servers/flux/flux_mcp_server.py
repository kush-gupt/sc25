#!/usr/bin/env python3
"""Flux MCP Server - Model Context Protocol server for Flux Framework."""
import asyncio
import json
import os
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from pydantic import AnyUrl
import logging

from flux_client import FluxClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flux-mcp-server")

# Initialize Flux client
flux_client = FluxClient()

# Create MCP server
server = Server("flux-mcp-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Flux MCP tools"""
    return [
        Tool(
            name="flux_submit_job",
            description="Submit a job to Flux Framework",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute"
                    },
                    "script": {
                        "type": "string",
                        "description": "Path to script file (if submitting script)"
                    },
                    "nodes": {
                        "type": "integer",
                        "description": "Number of nodes to request"
                    },
                    "tasks": {
                        "type": "integer",
                        "description": "Number of tasks to run"
                    },
                    "cores_per_task": {
                        "type": "integer",
                        "description": "Cores per task"
                    },
                    "time_limit": {
                        "type": "string",
                        "description": "Time limit (e.g., '1h', '30m')"
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Name for the job"
                    },
                    "output": {
                        "type": "string",
                        "description": "Output file path"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="flux_get_job",
            description="Get detailed information about a specific Flux job",
            inputSchema={
                "type": "object",
                "properties": {
                    "jobid": {
                        "type": "string",
                        "description": "Job ID to query (e.g., 'ƒXXXXXX')"
                    }
                },
                "required": ["jobid"]
            }
        ),
        Tool(
            name="flux_list_jobs",
            description="List all jobs in Flux",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Filter by state (active, inactive, running, pending, etc.)"
                    },
                    "user": {
                        "type": "string",
                        "description": "Filter by user"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="flux_cancel_job",
            description="Cancel a Flux job",
            inputSchema={
                "type": "object",
                "properties": {
                    "jobid": {
                        "type": "string",
                        "description": "Job ID to cancel"
                    }
                },
                "required": ["jobid"]
            }
        ),
        Tool(
            name="flux_get_queue",
            description="View current queue status and statistics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="flux_get_resources",
            description="List available resources in Flux",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="flux_job_attach",
            description="Get output from a completed Flux job",
            inputSchema={
                "type": "object",
                "properties": {
                    "jobid": {
                        "type": "string",
                        "description": "Job ID"
                    }
                },
                "required": ["jobid"]
            }
        ),
        Tool(
            name="flux_job_stats",
            description="Get performance metrics for a Flux job",
            inputSchema={
                "type": "object",
                "properties": {
                    "jobid": {
                        "type": "string",
                        "description": "Job ID"
                    }
                },
                "required": ["jobid"]
            }
        ),
        Tool(
            name="flux_submit_with_deps",
            description="Submit a Flux job with dependencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute"
                    },
                    "dependency_type": {
                        "type": "string",
                        "enum": ["afterok", "afterany", "after"],
                        "description": "Type of dependency"
                    },
                    "dependency_jobid": {
                        "type": "string",
                        "description": "Job ID to depend on"
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Name for the job"
                    }
                },
                "required": ["command", "dependency_type", "dependency_jobid"]
            }
        ),
        Tool(
            name="flux_bulk_submit",
            description="Submit multiple jobs to Flux",
            inputSchema={
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of commands to submit"
                    },
                    "job_name_prefix": {
                        "type": "string",
                        "description": "Prefix for job names"
                    },
                    "nodes": {
                        "type": "integer",
                        "description": "Number of nodes per job"
                    },
                    "tasks": {
                        "type": "integer",
                        "description": "Number of tasks per job"
                    }
                },
                "required": ["commands"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls"""
    try:
        if name == "flux_submit_job":
            result = flux_client.submit_job(
                command=arguments["command"],
                script=arguments.get("script"),
                nodes=arguments.get("nodes"),
                tasks=arguments.get("tasks"),
                cores_per_task=arguments.get("cores_per_task"),
                time_limit=arguments.get("time_limit"),
                job_name=arguments.get("job_name"),
                output=arguments.get("output")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_get_job":
            result = flux_client.get_job(arguments["jobid"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_list_jobs":
            result = flux_client.list_jobs(
                state=arguments.get("state"),
                user=arguments.get("user")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_cancel_job":
            result = flux_client.cancel_job(arguments["jobid"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_get_queue":
            result = flux_client.get_queue_status()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_get_resources":
            result = flux_client.get_resources()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_job_attach":
            result = flux_client.get_job_output(arguments["jobid"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_job_stats":
            result = flux_client.get_job_stats(arguments["jobid"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_submit_with_deps":
            result = flux_client.submit_with_dependencies(
                command=arguments["command"],
                dependency_type=arguments["dependency_type"],
                dependency_jobid=arguments["dependency_jobid"],
                job_name=arguments.get("job_name")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "flux_bulk_submit":
            # Prepare job parameters
            kwargs = {}
            if arguments.get("nodes"):
                kwargs["nodes"] = arguments["nodes"]
            if arguments.get("tasks"):
                kwargs["tasks"] = arguments["tasks"]
            if arguments.get("job_name_prefix"):
                # Add numbered suffix for each job
                commands_with_names = []
                for i, cmd in enumerate(arguments["commands"], 1):
                    kwargs_copy = kwargs.copy()
                    kwargs_copy["job_name"] = f"{arguments['job_name_prefix']}-{i}"
                    commands_with_names.append((cmd, kwargs_copy))
                
                # Submit each command with its parameters
                job_ids = []
                errors = []
                for cmd, job_kwargs in commands_with_names:
                    result = flux_client.submit_job(cmd, **job_kwargs)
                    if result.get("success"):
                        job_ids.append(result.get("jobid"))
                    else:
                        errors.append({"command": cmd, "error": result.get("error")})
                
                result = {
                    "success": len(errors) == 0,
                    "job_ids": job_ids,
                    "errors": errors if errors else None,
                    "submitted": len(job_ids),
                    "failed": len(errors)
                }
            else:
                result = flux_client.bulk_submit(arguments["commands"], **kwargs)
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2)
            )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e), "tool": name}, indent=2)
        )]

async def main():
    """Run the MCP server"""
    from mcp.server.streamable_http import StreamableHTTPServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import Response
    import uvicorn
    
    logger.info(f"Starting Flux MCP Server (namespace: {flux_client.namespace})")
    transport = StreamableHTTPServerTransport(mcp_session_id=None)
    
    async def mcp_endpoint(scope, receive, send):
        """MCP endpoint handler"""
        await transport.handle_request(scope, receive, send)
        async with transport.connect() as (read_stream, write_stream):
            try:
                await server.run(read_stream, write_stream, server.create_initialization_options())
            except Exception as e:
                logger.error(f"MCP error: {e}")
    
    async def health_check(request):
        return Response(
            content=json.dumps({"status": "healthy", "service": "flux-mcp-server"}),
            media_type="application/json"
        )
    
    app = Starlette(
        routes=[
            Route("/messages", endpoint=mcp_endpoint, methods=["GET", "POST", "DELETE"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
        ],
    )
    
    port = int(os.getenv("MCP_PORT", "5000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info(f"Listening on {host}:{port}")
    
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()

if __name__ == "__main__":
    asyncio.run(main())

