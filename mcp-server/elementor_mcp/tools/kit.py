from ..core.wp_client import WpClient
from ..envelope import ToolResult, ok


def kit_get(client: WpClient) -> ToolResult:
    return client.get("/kit")


def kit_set(client: WpClient, *, settings: dict) -> ToolResult:
    return client.put("/kit", json=settings)


def kit_promote_custom_colors(client, *, hex_colors: list[str]) -> ToolResult:
    """Add each new hex to Kit custom_colors (deduped). Returns the slot ids assigned."""
    if not hex_colors:
        return ok({"promoted": []})

    cur = client.get("/kit")
    if not cur.ok:
        return cur
    settings = cur.data if isinstance(cur.data, dict) else {}
    custom = list(settings.get("custom_colors") or [])
    existing_hexes = {c.get("color", "").upper() for c in custom}

    promoted = []
    next_index = sum(1 for c in custom if (c.get("_id") or "").startswith("mcp-custom-")) + 1
    for hex_color in hex_colors:
        normalized = hex_color.upper()
        if normalized in existing_hexes:
            continue
        slot = f"mcp-custom-{next_index}"
        next_index += 1
        custom.append({"_id": slot, "title": slot, "color": normalized})
        promoted.append({"hex": normalized, "slot": slot})
        existing_hexes.add(normalized)

    if not promoted:
        return ok({"promoted": []})

    settings["custom_colors"] = custom
    put = client.put("/kit", json=settings)
    if not put.ok:
        return put
    return ok({"promoted": promoted})
