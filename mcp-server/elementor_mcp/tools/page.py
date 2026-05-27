from ..core.wp_client import WpClient
from ..envelope import ToolResult


def page_list(client: WpClient, *, search: str | None = None, per_page: int | None = None) -> ToolResult:
    params: dict = {}
    if search is not None:
        params["search"] = search
    if per_page is not None:
        params["per_page"] = per_page
    return client.get("/pages", params=params or None)


def page_create(client: WpClient, *, title: str, profile_id: int | None = None) -> ToolResult:
    body: dict = {"title": title}
    if profile_id is not None:
        body["profile_id"] = profile_id
    return client.post("/pages", json=body)


def page_get(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}")


def page_delete(client: WpClient, *, page_id: int) -> ToolResult:
    return client.delete(f"/pages/{page_id}")
