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
            Tool(name="section_add", description="Append or insert a new section. When profile_id is set, the section JSON is normalized to the profile (colors → globals, fonts → globals, sizes → typography) and any overflow colors are promoted to Kit custom_colors. A diff report is included in the response.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                     "section_json":{"type":"object"},
                     "position":{"type":"integer"},
                     "profile_id":{"type":"integer"},
                     "normalize":{"type":"boolean"},
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
            Tool(name="kit_get", description="Read the current Elementor Kit settings.",
                 inputSchema={"type":"object","properties":{},"additionalProperties":False}),
            Tool(name="kit_set", description="Replace the Elementor Kit settings (raw, advanced).",
                 inputSchema={"type":"object","properties":{
                     "settings":{"type":"object"},
                 },"required":["settings"],"additionalProperties":False}),
            Tool(name="image_generate",
                 description="Generate an image at exact dimensions via OpenAI gpt-image-1 (or Unsplash fallback). Returns base64-encoded PNG bytes.",
                 inputSchema={"type":"object","properties":{
                     "prompt":{"type":"string"},
                     "width":{"type":"integer"},
                     "height":{"type":"integer"},
                     "prefer":{"type":"string","enum":["openai","unsplash"]},
                 },"required":["prompt","width","height"],"additionalProperties":False}),
            Tool(name="image_upload",
                 description="Upload a base64-encoded image to the WP Media Library. Returns the WP attachment id + source_url.",
                 inputSchema={"type":"object","properties":{
                     "content_b64":{"type":"string"},
                     "filename":{"type":"string"},
                     "mime":{"type":"string"},
                 },"required":["content_b64","filename"],"additionalProperties":False}),
            Tool(name="image_describe_slot",
                 description="List image-bearing slots in a section JSON (widget_image + section_background).",
                 inputSchema={"type":"object","properties":{
                     "section_json":{"type":"object"},
                 },"required":["section_json"],"additionalProperties":False}),
            Tool(name="template_search",
                 description="Search the template library by query + filters. Returns top-k template metadata rows.",
                 inputSchema={"type":"object","properties":{
                     "query":{"type":"string"},
                     "category":{"type":"string"},
                     "has_image":{"type":"boolean"},
                     "k":{"type":"integer"},
                 },"additionalProperties":False}),
            Tool(name="template_get",
                 description="Get a template's full JSON + indexed metadata by id.",
                 inputSchema={"type":"object","properties":{
                     "template_id":{"type":"string"},
                 },"required":["template_id"],"additionalProperties":False}),
            Tool(name="template_preview",
                 description="Get a template's preview URL (may be null in Stage B).",
                 inputSchema={"type":"object","properties":{
                     "template_id":{"type":"string"},
                 },"required":["template_id"],"additionalProperties":False}),
            Tool(name="template_list_categories",
                 description="List all distinct template categories with counts.",
                 inputSchema={"type":"object","properties":{},"additionalProperties":False}),
        ]

    @server.call_tool()
    async def _call(name: str, arguments: dict) -> list[TextContent]:
        from pathlib import Path as _Path

        from .tools.image import image_describe_slot, image_generate, image_upload
        from .tools.kit import kit_get, kit_set
        from .tools.template import (
            template_get,
            template_list_categories,
            template_preview,
            template_search,
        )
        _DB_PATH = _Path(__file__).resolve().parent / "data" / "index.db"
        _SRC_DIR = _Path(__file__).resolve().parent.parent.parent / "section-express-libr" / "pack" / "JSON Files"
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
        elif name == "kit_get":
            result = kit_get(client)
        elif name == "kit_set":
            result = kit_set(client, **arguments)
        elif name == "image_generate":
            result = image_generate(settings=settings, **arguments)
        elif name == "image_upload":
            result = image_upload(client=client, **arguments)
        elif name == "image_describe_slot":
            result = image_describe_slot(**arguments)
        elif name == "template_search":
            result = template_search(db_path=_DB_PATH, src_dir=_SRC_DIR, **arguments)
        elif name == "template_get":
            result = template_get(db_path=_DB_PATH, src_dir=_SRC_DIR, **arguments)
        elif name == "template_preview":
            result = template_preview(db_path=_DB_PATH, **arguments)
        elif name == "template_list_categories":
            result = template_list_categories(db_path=_DB_PATH)
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
