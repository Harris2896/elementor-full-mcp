from io import BytesIO

import httpx
import respx
from PIL import Image

from elementor_mcp.core.image.unsplash_fallback import generate_image_unsplash
from elementor_mcp.errors import ErrorCode


def _valid_png(w: int = 100, h: int = 100) -> bytes:
    """Generate a real decodable PNG of given size."""
    buf = BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, "PNG")
    return buf.getvalue()


@respx.mock
def test_unsplash_search_returns_first_hit_resized():
    respx.get("https://api.unsplash.com/search/photos").mock(
        return_value=httpx.Response(200, json={
            "results": [{"urls": {"raw": "https://images.unsplash.com/photo-abc"}}],
        })
    )
    respx.get("https://images.unsplash.com/photo-abc").mock(
        return_value=httpx.Response(200, content=_valid_png(800, 600))
    )
    result = generate_image_unsplash(
        query="cowboy hat", width=400, height=300, access_key="us-test",
    )
    assert result.ok is True, result.error
    assert result.data["mime"] == "image/png"
    img = Image.open(BytesIO(result.data["bytes"]))
    assert img.size == (400, 300)


@respx.mock
def test_unsplash_returns_failure_on_empty_results():
    respx.get("https://api.unsplash.com/search/photos").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    result = generate_image_unsplash(
        query="zzznopex", width=100, height=100, access_key="us-test",
    )
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value


def test_unsplash_returns_failure_when_no_key():
    result = generate_image_unsplash(query="x", width=100, height=100, access_key="")
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value
