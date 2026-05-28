from ..core.wp_client import WpClient
from ..envelope import ToolResult


def section_list(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}/sections")


def section_get(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.get(f"/pages/{page_id}/sections/{sid}")


def section_add(
    client: WpClient, *, page_id: int, section_json: dict, position: int | None = None,
) -> ToolResult:
    body: dict = {"json": section_json}
    if position is not None:
        body["position"] = position
    return client.post(f"/pages/{page_id}/sections", json=body)


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
