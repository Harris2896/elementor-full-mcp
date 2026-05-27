from ..core.wp_client import WpClient
from ..envelope import ToolResult


def auth_verify(client: WpClient) -> ToolResult:
    """Verify the WP API key works and return the WP user mapped to it."""
    return client.get("/auth/verify")
