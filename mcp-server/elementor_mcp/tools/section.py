from ..core.wp_client import WpClient
from ..envelope import ToolResult, ok


def section_list(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}/sections")


def section_get(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.get(f"/pages/{page_id}/sections/{sid}")


def _normalize_with_kit_overflow(
    *, client, section_json: dict, profile_id: int,
) -> ToolResult:
    """Fetch profile, normalize section, promote overflow colors to Kit custom_colors,
    then rewrite section globals to point at the new slots. Returns ToolResult({section, diff})."""
    from ..core.normalizer.normalize import normalize_section
    from .kit import kit_promote_custom_colors
    from .profile import profile_get

    prof = profile_get(client, profile_id=profile_id)
    if not prof.ok:
        return prof
    profile_data = (prof.data or {}).get("data") or {}

    normalized = normalize_section(section_json, profile_data)
    section = normalized["section"]
    diff = normalized["diff"]

    overflow_hexes = [c["hex"] for c in diff.get("colors_overflow", [])]
    promoted = kit_promote_custom_colors(client, hex_colors=overflow_hexes)
    if not promoted.ok:
        return promoted
    diff["colors_promoted"] = promoted.data.get("promoted", [])

    slot_by_hex = {p["hex"]: p["slot"] for p in diff["colors_promoted"]}
    if slot_by_hex:
        _swap_overflow_globals(section, slot_by_hex)
    return ok({"section": section, "diff": diff})


def _swap_overflow_globals(node: dict, slot_by_hex: dict[str, str]) -> None:
    settings = node.get("settings") or {}
    for k, v in list(settings.items()):
        if isinstance(v, str) and v.startswith("#") and v.upper() in slot_by_hex:
            slot = slot_by_hex[v.upper()]
            g = settings.setdefault("__globals__", {})
            g[k] = f"globals/colors?id={slot}"
            del settings[k]
    for child in node.get("elements", []) or []:
        _swap_overflow_globals(child, slot_by_hex)


def section_add(
    client,
    *,
    page_id: int,
    section_json: dict,
    position: int | None = None,
    profile_id: int | None = None,
    normalize: bool = True,
) -> ToolResult:
    diff = None
    if profile_id is not None and normalize:
        normalized = _normalize_with_kit_overflow(
            client=client, section_json=section_json, profile_id=profile_id,
        )
        if not normalized.ok:
            return normalized
        section_json = normalized.data["section"]
        diff = normalized.data["diff"]

    body: dict = {"json": section_json}
    if position is not None:
        body["position"] = position
    result = client.post(f"/pages/{page_id}/sections", json=body)
    if not result.ok:
        return result
    payload = dict(result.data) if isinstance(result.data, dict) else {"sid": None}
    if diff is not None:
        payload["diff"] = diff
    return ok(payload)


def section_update(client: WpClient, *, page_id: int, sid: str, section_json: dict) -> ToolResult:
    return client.put(f"/pages/{page_id}/sections/{sid}", json={"json": section_json})


def section_delete(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.delete(f"/pages/{page_id}/sections/{sid}")


def section_duplicate(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.post(f"/pages/{page_id}/sections/{sid}/duplicate")


def section_reorder(client: WpClient, *, page_id: int, order: list[str]) -> ToolResult:
    return client.post(f"/pages/{page_id}/sections/reorder", json={"order": order})


def section_history(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}/backups")


def section_restore(client: WpClient, *, page_id: int, version: int) -> ToolResult:
    return client.post(f"/pages/{page_id}/backups/{version}/restore", json={})
