#!/usr/bin/env python3
"""Slurm MCP Server - Model Context Protocol server for Slurm workload manager."""
import asyncio
import json
import os
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from pydantic import AnyUrl
import logging

from slurm_client import SlurmClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("slurm-mcp-server")

# Initialize Slurm client
slurm_client = SlurmClient()

# Create MCP server
server = Server("slurm-mcp-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Slurm MCP tools"""
    return [
        Tool(
            name="slurm_submit_job",
            description="Submit a batch job to Slurm with a script",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Job script content (including shebang)"
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Name for the job"
                    },
                    "partition": {
                        "type": "string",
                        "description": "Partition to submit to"
                    },
                    "nodes": {
                        "type": "integer",
                        "description": "Number of nodes to request"
                    },
                    "tasks": {
                        "type": "integer",
                        "description": "Number of tasks to run"
                    },
                    "memory": {
                        "type": "string",
                        "description": "Memory per CPU (e.g., '1G', '512M')"
                    },
                    "time_limit": {
                        "type": "integer",
                        "description": "Time limit in minutes"
                    },
                    "output": {
                        "type": "string",
                        "description": "Path for stdout"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for the job"
                    }
                },
                "required": ["script"]
            }
        ),
        Tool(
            name="slurm_get_job",
            description="Get detailed information about a specific Slurm job",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID to query"
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="slurm_list_jobs",
            description="List all jobs in the Slurm queue",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "Filter by username"
                    },
                    "state": {
                        "type": "string",
                        "description": "Filter by job state (PENDING, RUNNING, COMPLETED, etc.)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="slurm_cancel_job",
            description="Cancel a running or pending Slurm job",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID to cancel"
                    },
                    "signal": {
                        "type": "string",
                        "description": "Signal to send (default: SIGTERM)"
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="slurm_get_queue",
            description="View current queue status and statistics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="slurm_get_nodes",
            description="List compute nodes and their status",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Specific node name to query (optional)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="slurm_submit_array",
            description="Submit an array job to Slurm",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Job script content with array task variable support"
                    },
                    "array_spec": {
                        "type": "string",
                        "description": "Array specification (e.g., '1-10', '1-10:2')"
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Name for the array job"
                    },
                    "max_concurrent": {
                        "type": "integer",
                        "description": "Maximum number of concurrent array tasks"
                    }
                },
                "required": ["script", "array_spec"]
            }
        ),
        Tool(
            name="slurm_get_accounting",
            description="Get job accounting data (requires slurmdbd)",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Specific job ID to query (optional)"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time for accounting query"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time for accounting query"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="slurm_job_output",
            description="Retrieve stdout/stderr from a job",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID"
                    },
                    "output_type": {
                        "type": "string",
                        "enum": ["stdout", "stderr", "both"],
                        "description": "Type of output to retrieve"
                    }
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="slurm_resource_info",
            description="Get partition and resource information",
            inputSchema={
                "type": "object",
                "properties": {
                    "partition": {
                        "type": "string",
                        "description": "Specific partition name to query (optional)"
                    }
                },
                "required": []
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls"""
    try:
        if name == "slurm_submit_job":
            script_content = arguments.get("script")
            
            if not script_content:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Script content is required"}, indent=2)
                )]
            
            result = slurm_client.submit_job(
                script=script_content,
                job_name=arguments.get("job_name"),
                partition=arguments.get("partition"),
                nodes=arguments.get("nodes"),
                tasks=arguments.get("tasks"),
                memory=arguments.get("memory"),
                time_limit=arguments.get("time_limit"),
                output=arguments.get("output"),
                working_dir=arguments.get("working_dir")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_get_job":
            result = slurm_client.get_job(arguments["job_id"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_list_jobs":
            result = slurm_client.list_jobs(
                user=arguments.get("user"),
                state=arguments.get("state")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_cancel_job":
            result = slurm_client.cancel_job(
                job_id=arguments["job_id"],
                signal=arguments.get("signal")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_get_queue":
            result = slurm_client.list_jobs()
            # Parse and format queue statistics
            if "jobs" in result:
                jobs = result.get("jobs", [])
                stats = {
                    "total_jobs": len(jobs),
                    "running": sum(1 for j in jobs if j.get("job_state") == "RUNNING"),
                    "pending": sum(1 for j in jobs if j.get("job_state") == "PENDING"),
                    "completed": sum(1 for j in jobs if j.get("job_state") == "COMPLETED"),
                    "jobs": jobs[:20]  # Return first 20 jobs
                }
                return [TextContent(type="text", text=json.dumps(stats, indent=2))]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_get_nodes":
            if arguments.get("node_name"):
                result = slurm_client.get_node(arguments["node_name"])
            else:
                result = slurm_client.get_nodes()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_submit_array":
            script_content = arguments.get("script")
            
            if not script_content:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Script content is required"}, indent=2)
                )]
            
            result = slurm_client.submit_array_job(
                script=script_content,
                array_spec=arguments["array_spec"],
                job_name=arguments.get("job_name")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_get_accounting":
            result = slurm_client.get_accounting(
                job_id=arguments.get("job_id"),
                start_time=arguments.get("start_time"),
                end_time=arguments.get("end_time")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_job_output":
            job_id = arguments["job_id"]
            output_type = arguments.get("output_type", "stdout")
            
            # Get job output via kubectl
            result = slurm_client.get_job_output(job_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "slurm_resource_info":
            if arguments.get("partition"):
                result = slurm_client.get_partition(arguments["partition"])
            else:
                result = slurm_client.get_partitions()
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
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import Response, JSONResponse
    from sse_starlette import EventSourceResponse
    import uvicorn
    
    logger.info(f"Starting Slurm MCP Server (API: {slurm_client.base_url})")
    
    async def handle_mcp_post(request):
        """Handle POST requests"""
        try:
            body = await request.json()
            
            if body.get("method", "").startswith("notifications/"):
                return Response(status_code=202)
            
            # Handle initialize
            if body.get("method") == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "slurm-mcp-server",
                            "version": "1.0.0"
                        }
                    }
                }
                return JSONResponse(response)
            
            # Handle tools/list
            elif body.get("method") == "tools/list":
                tools = await list_tools()
                response = {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "tools": [t.model_dump(exclude_none=True) for t in tools]
                    }
                }
                return JSONResponse(response)
            
            # Handle tools/call
            elif body.get("method") == "tools/call":
                params = body.get("params", {})
                result = await call_tool(params.get("name"), params.get("arguments", {}))
                response = {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "content": [r.model_dump(exclude_none=True) for r in result]
                    }
                }
                return JSONResponse(response)
            
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {body.get('method')}"
                    }
                }, status_code=400)
                
        except Exception as e:
            logger.error(f"MCP error: {e}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id") if 'body' in locals() else None,
                "error": {"code": -32603, "message": str(e)}
            }, status_code=500)
    
    async def handle_mcp_get(request):
        """Handle GET requests (SSE)"""
        async def event_generator():
            while True:
                await asyncio.sleep(30)
                yield {"event": "ping", "data": ""}
        return EventSourceResponse(event_generator())
    
    async def health_check(request):
        return JSONResponse({"status": "healthy", "service": "slurm-mcp-server"})
    
    app = Starlette(
        routes=[
            Route("/messages", endpoint=handle_mcp_post, methods=["POST"]),
            Route("/messages", endpoint=handle_mcp_get, methods=["GET"]),
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

