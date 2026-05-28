import json
import uuid
from pathlib import Path

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.page import page_create, page_delete
from elementor_mcp.tools.profile import profile_apply, profile_create, profile_delete
from elementor_mcp.tools.section import section_add, section_get

FIX = Path(__file__).parent.parent / "fixtures"


def _profile_payload(name: str) -> dict:
    data = json.loads((FIX / "profiles" / "stacks-western.json").read_text())
    data["name"] = name
    return data


def test_section_add_with_profile_normalizes_colors(live_settings):
    client = WpClient(live_settings)

    pname = f"itest-norm-{uuid.uuid4().hex[:6]}"
    p_res = profile_create(client, profile=_profile_payload(pname))
    assert p_res.ok, p_res.error
    pid = p_res.data["id"]
    assert profile_apply(client, profile_id=pid).ok

    pg = page_create(client, title=f"itest-norm-page-{uuid.uuid4().hex[:6]}", profile_id=pid)
    assert pg.ok, pg.error
    page_id = pg.data["id"]

    sid = uuid.uuid4().hex[:8]
    raw_section = {
        "id": sid, "elType": "section",
        "settings": {
            "_title": "Hero",
            "background_color": "#8B4513",    # primary, should snap
            "title_color":      "#00FF00",    # neon green, should overflow
        },
        "elements": [{
            "id": uuid.uuid4().hex[:8], "elType": "widget", "widgetType": "heading",
            "settings": {
                "title": "Test",
                "typography_font_family": "Playfair Display",
                "typography_font_size": {"unit": "px", "size": 64},
            },
            "elements": [],
        }],
    }

    add = section_add(client, page_id=page_id, section_json=raw_section, profile_id=pid)
    assert add.ok, add.error
    assert "diff" in add.data
    diff = add.data["diff"]
    assert any(r.get("to") == "primary" for r in diff.get("colors_remapped", []))
    assert any(p.get("hex") == "#00FF00" for p in diff.get("colors_promoted", []))

    fetched = section_get(client, page_id=page_id, sid=sid)
    assert fetched.ok, fetched.error
    s = fetched.data
    # background_color was snapped to primary
    assert "background_color" not in s["settings"]
    assert s["settings"]["__globals__"]["background_color"] == "globals/colors?id=primary"
    # title_color was promoted to a custom slot
    title_ref = s["settings"]["__globals__"]["title_color"]
    assert title_ref.startswith("globals/colors?id=mcp-custom-")

    # cleanup
    page_delete(client, page_id=page_id)
    profile_delete(client, profile_id=pid)
