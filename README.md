# Elementor MCP

Python MCP server + WordPress plugin for AI-driven Elementor page authoring.

See `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` for the design.

## Quickstart

```bash
make plugin-install
make mcp-install
make wp-up                 # boots wp-env on http://localhost:8888
# In WP admin (login admin/password): activate "Elementor MCP Bridge",
# go to Elementor MCP -> API Keys -> Generate, copy the key.
cp mcp-server/.env.example mcp-server/.env  # paste API key
make mcp-test
```
