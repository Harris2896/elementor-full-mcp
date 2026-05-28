import httpx
import respx

from elementor_mcp.config import Settings
from elementor_mcp.core.image.media_upload import upload_image_to_wp
from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.errors import ErrorCode


def _settings():
    return Settings(
        wp_url="http://localhost:8888",
        wp_api_key="emcp_test_key",
        log_level="info",
        http_timeout=5,
    )


@respx.mock
def test_upload_posts_to_wp_media_endpoint_with_attachment_header():
    route = respx.post("http://localhost:8888/wp-json/wp/v2/media").mock(
        return_value=httpx.Response(201, json={"id": 42, "source_url": "http://x/img.png"})
    )
    client = WpClient(_settings())
    res = upload_image_to_wp(client, content=b"\x89PNGfake", filename="cow.png")
    assert res.ok is True
    assert res.data["id"] == 42
    assert res.data["source_url"] == "http://x/img.png"
    assert route.called
    sent_headers = route.calls.last.request.headers
    assert sent_headers["Content-Type"] == "image/png"
    assert 'attachment; filename="cow.png"' in sent_headers["Content-Disposition"]


@respx.mock
def test_upload_returns_failure_envelope_on_401():
    respx.post("http://localhost:8888/wp-json/wp/v2/media").mock(
        return_value=httpx.Response(401, json={"code": "rest_forbidden"})
    )
    client = WpClient(_settings())
    res = upload_image_to_wp(client, content=b"x", filename="x.png")
    assert res.ok is False
    assert res.error.code == ErrorCode.E_WP_AUTH.value
