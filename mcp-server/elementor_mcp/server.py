import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import load
from .core.wp_client import WpClient
from .tools.auth import auth_verify


def build_server() -> Server:
    settings = load()
    client = WpClient(settings)
    server: Server = Server("elementor-mcp")

    @server.list_tools()
    async def _list() -> list[Tool]:
        return [
            Tool(
                name="auth_verify",
                description="Verify the configured WP_API_KEY works. Returns the WP user it maps to.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
        ]

    @server.call_tool()
    async def _call(name: str, arguments: dict) -> list[TextContent]:
        if name == "auth_verify":
            result = auth_verify(client)
        else:
            return [TextContent(type="text", text=json.dumps({
                "ok": False,
                "error": {"code": "E_INTERNAL", "message": f"unknown tool: {name}"},
            }))]
        return [TextContent(type="text", text=result.model_dump_json())]

    return server


def main() -> None:
    import asyncio

    async def _run():
        server = build_server()
        async with stdio_server() as (read, write):
            await server.run(
                read,
                write,
                server.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
