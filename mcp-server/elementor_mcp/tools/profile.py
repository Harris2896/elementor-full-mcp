from ..core.wp_client import WpClient
from ..envelope import ToolResult


def profile_list(client: WpClient) -> ToolResult:
    return client.get("/profiles")


def profile_get(client: WpClient, *, profile_id: int) -> ToolResult:
    return client.get(f"/profiles/{profile_id}")


def profile_create(client: WpClient, *, profile: dict) -> ToolResult:
    return client.post("/profiles", json=profile)


def profile_update(client: WpClient, *, profile_id: int, profile: dict) -> ToolResult:
    return client.put(f"/profiles/{profile_id}", json=profile)


def profile_delete(client: WpClient, *, profile_id: int) -> ToolResult:
    return client.delete(f"/profiles/{profile_id}")


def profile_apply(client: WpClient, *, profile_id: int) -> ToolResult:
    return client.post(f"/profiles/{profile_id}/apply", json={})
