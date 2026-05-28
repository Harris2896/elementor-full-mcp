from ..core.wp_client import WpClient
from ..envelope import ToolResult


def kit_get(client: WpClient) -> ToolResult:
    return client.get("/kit")


def kit_set(client: WpClient, *, settings: dict) -> ToolResult:
    return client.put("/kit", json=settings)
