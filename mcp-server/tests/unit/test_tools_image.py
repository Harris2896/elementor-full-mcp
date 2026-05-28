import base64
from unittest.mock import MagicMock, patch

from elementor_mcp.config import Settings
from elementor_mcp.envelope import fail, ok
from elementor_mcp.errors import ErrorCode
from elementor_mcp.tools.image import (
    image_describe_slot,
    image_generate,
    image_upload,
)


def _settings(openai_key: str = "sk-x", unsplash_key: str = "us-x"):
    return Settings(
        wp_url="http://localhost:8888",
        wp_api_key="emcp_t_t",
        log_level="info",
        http_timeout=5,
        openai_api_key=openai_key,
        unsplash_access_key=unsplash_key,
    )


def test_image_generate_uses_openai_first():
    with patch("elementor_mcp.tools.image.generate_image_openai") as m_openai, \
         patch("elementor_mcp.tools.image.generate_image_unsplash") as m_un:
        m_openai.return_value = ok({"bytes": b"openai-png", "mime": "image/png", "width": 100, "height": 100})
        res = image_generate(
            settings=_settings(), prompt="a hat", width=100, height=100, prefer="openai",
        )
        assert res.ok is True
        assert res.data["source"] == "openai"
        assert base64.b64decode(res.data["bytes_b64"]) == b"openai-png"
        m_un.assert_not_called()


def test_image_generate_falls_back_to_unsplash_on_openai_failure():
    with patch("elementor_mcp.tools.image.generate_image_openai") as m_openai, \
         patch("elementor_mcp.tools.image.generate_image_unsplash") as m_un:
        m_openai.return_value = fail(ErrorCode.E_IMAGE_GEN_FAILED, "openai down")
        m_un.return_value = ok({"bytes": b"unsplash-png", "mime": "image/png", "width": 100, "height": 100})
        res = image_generate(
            settings=_settings(), prompt="a hat", width=100, height=100, prefer="openai",
        )
        assert res.ok is True
        assert res.data["source"] == "unsplash"


def test_image_generate_returns_failure_when_both_unavailable():
    with patch("elementor_mcp.tools.image.generate_image_openai") as m_openai, \
         patch("elementor_mcp.tools.image.generate_image_unsplash") as m_un:
        m_openai.return_value = fail(ErrorCode.E_IMAGE_GEN_FAILED, "no key")
        m_un.return_value = fail(ErrorCode.E_IMAGE_GEN_FAILED, "no key")
        res = image_generate(
            settings=_settings("", ""), prompt="x", width=10, height=10,
        )
        assert res.ok is False
        assert res.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value


def test_image_upload_decodes_b64_and_calls_uploader():
    client = MagicMock()
    with patch("elementor_mcp.tools.image.upload_image_to_wp") as m_up:
        m_up.return_value = ok({"id": 5, "source_url": "http://x.png"})
        b64 = base64.b64encode(b"some-png-bytes").decode("ascii")
        res = image_upload(client=client, content_b64=b64, filename="hero.png")
        assert res.ok is True
        assert res.data["id"] == 5
        kwargs = m_up.call_args.kwargs
        assert kwargs["content"] == b"some-png-bytes"
        assert kwargs["filename"] == "hero.png"


def test_image_describe_slot_returns_list():
    section = {
        "id": "abc", "elType": "section", "settings": {}, "elements": [
            {"id": "c1", "elType": "column", "settings": {}, "elements": [
                {"id": "w1", "elType": "widget", "widgetType": "image",
                 "settings": {"image": {"url": "http://x/p.png", "id": 7}}, "elements": []}
            ]}
        ]
    }
    res = image_describe_slot(section_json=section)
    assert res.ok is True
    assert len(res.data["slots"]) == 1
    assert res.data["slots"][0]["widget_id"] == "w1"
