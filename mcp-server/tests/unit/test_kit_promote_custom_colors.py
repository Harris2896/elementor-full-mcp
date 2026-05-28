from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.kit import kit_promote_custom_colors


def test_promote_adds_new_colors_to_existing_kit():
    client = MagicMock()
    client.get.return_value = ok({"custom_colors": [{"_id": "muted", "color": "#9F9F9F"}]})
    client.put.return_value = ok({"kit_post_id": 5})

    res = kit_promote_custom_colors(client, hex_colors=["#00FF00", "#FF00FF"])

    assert res.ok is True
    assert len(res.data["promoted"]) == 2
    assert res.data["promoted"][0]["hex"] == "#00FF00"
    assert res.data["promoted"][0]["slot"].startswith("mcp-custom-")

    sent = client.put.call_args.kwargs["json"]
    colors = sent["custom_colors"]
    assert len(colors) == 3
    assert any(c["color"] == "#9F9F9F" for c in colors)
    assert any(c["color"] == "#00FF00" for c in colors)


def test_promote_skips_duplicates():
    client = MagicMock()
    client.get.return_value = ok({"custom_colors": [{"_id": "muted", "color": "#9F9F9F"}]})
    client.put.return_value = ok({"kit_post_id": 5})

    res = kit_promote_custom_colors(client, hex_colors=["#9F9F9F", "#00FF00"])

    sent = client.put.call_args.kwargs["json"]
    assert len(sent["custom_colors"]) == 2
    assert len(res.data["promoted"]) == 1
    assert res.data["promoted"][0]["hex"] == "#00FF00"


def test_promote_returns_empty_when_no_overflow():
    client = MagicMock()
    res = kit_promote_custom_colors(client, hex_colors=[])
    assert res.ok is True
    assert res.data["promoted"] == []
    client.get.assert_not_called()
    client.put.assert_not_called()
