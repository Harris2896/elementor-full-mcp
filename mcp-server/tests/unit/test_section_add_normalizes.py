from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.section import section_add


def test_section_add_without_profile_id_skips_normalization():
    client = MagicMock()
    client.post.return_value = ok({"sid": "abc"})
    section_json = {"id": "abc", "elType": "section", "settings": {}, "elements": []}
    res = section_add(client, page_id=1, section_json=section_json)
    assert res.ok is True
    body = client.post.call_args.kwargs["json"]
    assert body["json"]["id"] == "abc"


def test_section_add_with_profile_id_returns_diff_in_response(monkeypatch):
    from elementor_mcp.tools import section as section_mod

    called: dict = {}

    def fake_normalize(*, client, section_json, profile_id):
        called["was_called"] = True
        return ok({
            "section": {"id": "abc", "elType": "section", "settings": {"__globals__": {"x": "y"}}, "elements": []},
            "diff": {"colors_remapped": [{"to": "primary"}], "colors_promoted": [], "tablet_stripped": 0},
        })

    monkeypatch.setattr(section_mod, "_normalize_with_kit_overflow", fake_normalize)
    client = MagicMock()
    client.post.return_value = ok({"sid": "abc"})
    section_json = {"id": "abc", "elType": "section", "settings": {"title_color": "#FF0000"}, "elements": []}
    res = section_add(client, page_id=1, section_json=section_json, profile_id=7)
    assert res.ok is True
    assert called.get("was_called") is True
    body = client.post.call_args.kwargs["json"]
    assert "__globals__" in body["json"]["settings"]
    assert "diff" in res.data
