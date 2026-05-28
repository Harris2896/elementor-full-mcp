import base64

import httpx

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.image import image_upload


def _tiny_png() -> bytes:
    """A small valid PNG generated via Pillow."""
    from io import BytesIO

    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (4, 4), (100, 50, 25)).save(buf, "PNG")
    return buf.getvalue()


def test_upload_image_to_wp_media_returns_reachable_url(live_settings):
    client = WpClient(live_settings)
    b64 = base64.b64encode(_tiny_png()).decode("ascii")
    res = image_upload(client=client, content_b64=b64, filename="emcp-itest.png")
    assert res.ok is True, res.error
    media_id = res.data["id"]
    url = res.data["source_url"]
    assert media_id > 0
    # The returned URL should be fetchable
    head = httpx.head(url, timeout=10)
    assert head.status_code == 200
