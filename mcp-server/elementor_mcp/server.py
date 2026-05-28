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
            Tool(
                name="profile_list",
                description="List all Kit profiles available on the configured site.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Tool(
                name="profile_get",
                description="Get one profile by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile_id": {"type": "integer"}},
                    "required": ["profile_id"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_create",
                description="Create a new profile. Body must conform to profile schema.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile": {"type": "object"}},
                    "required": ["profile"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_update",
                description="Replace a profile (full body).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "profile_id": {"type": "integer"},
                        "profile":    {"type": "object"},
                    },
                    "required": ["profile_id", "profile"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_delete",
                description="Delete a profile by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile_id": {"type": "integer"}},
                    "required": ["profile_id"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_apply",
                description="Write the profile's colors/fonts/typography into the active Elementor Kit.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile_id": {"type": "integer"}},
                    "required": ["profile_id"], "additionalProperties": False,
                },
            ),
            Tool(
                name="page_list",
                description="List Elementor-enabled pages.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "search": {"type": "string"},
                        "per_page": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="page_create",
                description="Create a new Elementor-enabled page.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "profile_id": {"type": "integer"},
                    },
                    "required": ["title"], "additionalProperties": False,
                },
            ),
            Tool(
                name="page_get",
                description="Get one page by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {"page_id": {"type": "integer"}},
                    "required": ["page_id"], "additionalProperties": False,
                },
            ),
            Tool(
                name="page_delete",
                description="Delete a page by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {"page_id": {"type": "integer"}},
                    "required": ["page_id"], "additionalProperties": False,
                },
            ),
            Tool(name="section_list", description="List flat section summaries for a page.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                 },"required":["page_id"],"additionalProperties":False}),
            Tool(name="section_get", description="Get a single section's full JSON.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                 },"required":["page_id","sid"],"additionalProperties":False}),
            Tool(name="section_add", description="Append or insert a new section.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                     "section_json":{"type":"object"},
                     "position":{"type":"integer"},
                 },"required":["page_id","section_json"],"additionalProperties":False}),
            Tool(name="section_update", description="Replace a section by id.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                     "section_json":{"type":"object"},
                 },"required":["page_id","sid","section_json"],"additionalProperties":False}),
            Tool(name="section_delete", description="Delete a section by id.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                 },"required":["page_id","sid"],"additionalProperties":False}),
            Tool(name="section_duplicate", description="Duplicate a section in place (right after).",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                 },"required":["page_id","sid"],"additionalProperties":False}),
            Tool(name="section_reorder", description="Reorder sections.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                     "order":{"type":"array","items":{"type":"string"}},
                 },"required":["page_id","order"],"additionalProperties":False}),
            Tool(name="section_history", description="List the last 5 backups for a page.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                 },"required":["page_id"],"additionalProperties":False}),
            Tool(name="section_restore", description="Restore a backup version.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"version":{"type":"integer"},
                 },"required":["page_id","version"],"additionalProperties":False}),
        ]

    @server.call_tool()
    async def _call(name: str, arguments: dict) -> list[TextContent]:
        from .tools.page import page_create, page_delete, page_get, page_list
        from .tools.profile import (
            profile_apply,
            profile_create,
            profile_delete,
            profile_get,
            profile_list,
            profile_update,
        )
        from .tools.section import (
            section_add,
            section_delete,
            section_duplicate,
            section_get,
            section_history,
            section_list,
            section_reorder,
            section_restore,
            section_update,
        )
        if name == "auth_verify":
            result = auth_verify(client)
        elif name == "profile_list":
            result = profile_list(client)
        elif name == "profile_get":
            result = profile_get(client, **arguments)
        elif name == "profile_create":
            result = profile_create(client, **arguments)
        elif name == "profile_update":
            result = profile_update(client, **arguments)
        elif name == "profile_delete":
            result = profile_delete(client, **arguments)
        elif name == "profile_apply":
            result = profile_apply(client, **arguments)
        elif name == "page_list":
            result = page_list(client, **arguments)
        elif name == "page_create":
            result = page_create(client, **arguments)
        elif name == "page_get":
            result = page_get(client, **arguments)
        elif name == "page_delete":
            result = page_delete(client, **arguments)
        elif name == "section_list":
            result = section_list(client, **arguments)
        elif name == "section_get":
            result = section_get(client, **arguments)
        elif name == "section_add":
            result = section_add(client, **arguments)
        elif name == "section_update":
            result = section_update(client, **arguments)
        elif name == "section_delete":
            result = section_delete(client, **arguments)
        elif name == "section_duplicate":
            result = section_duplicate(client, **arguments)
        elif name == "section_reorder":
            result = section_reorder(client, **arguments)
        elif name == "section_history":
            result = section_history(client, **arguments)
        elif name == "section_restore":
            result = section_restore(client, **arguments)
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
