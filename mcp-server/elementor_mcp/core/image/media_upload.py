from ...envelope import ToolResult
from ..wp_client import WpClient


def upload_image_to_wp(
    client: WpClient,
    *,
    content: bytes,
    filename: str,
    mime: str = "image/png",
) -> ToolResult:
    """Upload an image to the WP Media Library via /wp/v2/media.

    Returns the full attachment JSON on success (id, source_url, media_details, ...).
    """
    return client.post_binary(
        "/media",
        content=content,
        filename=filename,
        content_type=mime,
        wp_native=True,
    )
