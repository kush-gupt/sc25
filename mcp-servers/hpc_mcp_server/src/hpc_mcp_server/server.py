"""Unified MCP server entrypoint following rdwj/mcp-server-template structure."""
from __future__ import annotations

import asyncio
import logging
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .core.app import mcp
from . import tools
from .core.settings import load_settings

logger = logging.getLogger("hpc-mcp-server")
logging.basicConfig(level=logging.INFO)


async def create_app() -> Starlette:
    settings = load_settings()
    app = mcp.http_app(path="/messages", transport="http", stateless_http=True)

    async def health(_: object):
        return JSONResponse({"status": "healthy", "service": "hpc-mcp-server"})

    app.router.routes.append(Route("/health", health))
    return app


def run() -> None:
    import uvicorn

    settings = load_settings()
    app = asyncio.run(create_app())

    uvicorn.run(app, host=settings.server.host, port=settings.server.port, log_level="info")


if __name__ == "__main__":
    run()
