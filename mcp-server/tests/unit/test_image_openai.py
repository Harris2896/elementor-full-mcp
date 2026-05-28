import base64
from io import BytesIO
from unittest.mock import MagicMock, patch

from PIL import Image

from elementor_mcp.core.image.openai_gen import generate_image_openai
from elementor_mcp.errors import ErrorCode


def _fake_b64(width: int, height: int) -> str:
    # Tiny valid PNG of the given size — generated via Pillow so the bytes
    # are guaranteed valid (the hand-rolled byte literal in the original
    # task spec had a corrupted IDAT chunk).
    buf = BytesIO()
    Image.new("RGB", (width, height), (128, 128, 128)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_generate_returns_png_bytes_at_requested_size():
    fake_client = MagicMock()
    fake_client.images.generate.return_value = MagicMock(
        data=[MagicMock(b64_json=_fake_b64(1024, 1024))],
    )
    with patch("elementor_mcp.core.image.openai_gen.OpenAI", return_value=fake_client):
        result = generate_image_openai(
            prompt="a cowboy hat",
            width=1920,
            height=800,
            api_key="sk-test",
        )
    assert result.ok is True
    assert result.data["mime"] == "image/png"
    # Verify bytes round-trip through Pillow at the requested final size.
    img = Image.open(BytesIO(result.data["bytes"]))
    assert img.size == (1920, 800)


def test_generate_returns_e_image_gen_failed_on_openai_error():
    fake_client = MagicMock()
    fake_client.images.generate.side_effect = RuntimeError("rate limited")
    with patch("elementor_mcp.core.image.openai_gen.OpenAI", return_value=fake_client):
        result = generate_image_openai(prompt="x", width=512, height=512, api_key="sk-test")
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value


def test_generate_returns_failure_when_no_api_key():
    result = generate_image_openai(prompt="x", width=512, height=512, api_key="")
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value
    assert "no openai api key" in result.error.message.lower()
