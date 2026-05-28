# Elementor MCP

Python MCP server + WordPress plugin for AI-driven Elementor page authoring.

See `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` for the design.

## Quickstart

```bash
make plugin-install
make mcp-install
make wp-up                 # boots wp-env on http://localhost:8888
docker exec wp-env-elememtor-full-mcp-44381f72-cli-1 wp plugin activate wp-plugin
docker exec wp-env-elememtor-full-mcp-44381f72-cli-1 wp rewrite structure '/%postname%/'

# Mint an API key:
KEY=$(docker exec wp-env-elememtor-full-mcp-44381f72-cli-1 \
  wp eval 'require_once ABSPATH . "wp-content/plugins/wp-plugin/elementor-mcp-bridge.php"; \
           echo (new \ElementorMCP\Api_Keys())->generate(1, "dev", ["read","write"])["raw"];')
echo "$KEY"

# Configure MCP:
cp mcp-server/.env.example mcp-server/.env
# edit .env, paste $KEY into WP_API_KEY

# Register with Claude Code:
claude mcp add elementor -s user -- python -m elementor_mcp.server

# Verify integration:
make plugin-test    # 77 PHPUnit tests
make mcp-test       # 33 pytest tests
EMCP_TEST_API_KEY="$KEY" EMCP_TEST_WP_URL=http://localhost:8888 \
  cd mcp-server && uv run pytest tests/integration -v
```

## MCP tools (after Phase 1a)

- **Auth:** `auth_verify`
- **Profiles:** `profile_list`, `profile_get`, `profile_create`, `profile_update`, `profile_delete`, `profile_apply`
- **Pages:** `page_list`, `page_create`, `page_get`, `page_delete`
- **Sections:** `section_list`, `section_get`, `section_add`, `section_update`, `section_delete`, `section_duplicate`, `section_reorder`, `section_history`, `section_restore`
- **Kit (raw):** `kit_get`, `kit_set`
