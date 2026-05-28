import uuid

import pytest

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.kit import kit_get
from elementor_mcp.tools.page import page_create, page_delete
from elementor_mcp.tools.profile import (
    profile_apply,
    profile_create,
    profile_delete,
    profile_get,
)
from elementor_mcp.tools.section import (
    section_add,
    section_delete,
    section_history,
    section_list,
    section_reorder,
    section_restore,
)


@pytest.fixture
def client(live_settings):
    return WpClient(live_settings)


def _profile_payload(name: str) -> dict:
    return {
        "name": name,
        "colors": {"primary":"#0066FF","secondary":"#00C2A8","text":"#1A1A1A","accent":"#FFD60A","background":"#FFFFFF","custom":[]},
        "fonts": {"primary":{"family":"Inter","source":"google","weights":[400,700]},"secondary":{"family":"Manrope","source":"google","weights":[400,700]}},
        "typography": {
            "h1":{"size":64,"mobile":36,"weight":700,"line_height":1.1},
            "h2":{"size":48,"mobile":28,"weight":700,"line_height":1.15},
            "h3":{"size":32,"mobile":22,"weight":600,"line_height":1.2},
            "body":{"size":17,"mobile":15,"weight":500,"line_height":1.6},
            "small":{"size":14,"mobile":12,"weight":500,"line_height":1.5},
        },
        "layout":{"container_width":1290,"content_width":1200,"section_padding":{"top":80,"bottom":80},"section_padding_mobile":{"top":40,"bottom":40}},
        "breakpoints":{"mobile":767,"desktop":1290},
        "buttons":{"border_radius":0,"padding_x":32,"padding_y":16},
    }


def _section_json(sid: str, title: str) -> dict:
    return {
        "id": sid,
        "elType": "section",
        "settings": {"_title": title},
        "elements": [],
    }


def test_full_roundtrip(client):
    # 1. Create + apply profile
    profile_name = f"itest-{uuid.uuid4().hex[:6]}"
    created = profile_create(client, profile=_profile_payload(profile_name))
    assert created.ok, created.error
    pid = created.data["id"]

    fetched = profile_get(client, profile_id=pid)
    assert fetched.ok and fetched.data["name"] == profile_name

    applied = profile_apply(client, profile_id=pid)
    assert applied.ok and applied.data["kit_post_id"] > 0

    # Verify kit settings reflect profile
    kit = kit_get(client)
    assert kit.ok and len(kit.data.get("system_colors", [])) >= 4

    # 2. Create page
    page_title = f"itest-page-{uuid.uuid4().hex[:6]}"
    created_page = page_create(client, title=page_title, profile_id=pid)
    assert created_page.ok, created_page.error
    page_id = created_page.data["id"]

    # 3. Add two sections
    sid_a = uuid.uuid4().hex[:8]
    sid_b = uuid.uuid4().hex[:8]
    assert section_add(client, page_id=page_id, section_json=_section_json(sid_a, "A")).ok
    assert section_add(client, page_id=page_id, section_json=_section_json(sid_b, "B")).ok

    listed = section_list(client, page_id=page_id)
    assert listed.ok and len(listed.data) == 2

    # 4. Reorder, then delete one
    assert section_reorder(client, page_id=page_id, order=[sid_b, sid_a]).ok
    after_reorder = section_list(client, page_id=page_id)
    assert after_reorder.data[0]["sid"] == sid_b

    assert section_delete(client, page_id=page_id, sid=sid_a).ok

    # 5. Backup history should have entries from the mutations above
    history = section_history(client, page_id=page_id)
    assert history.ok and len(history.data) >= 1
    last_version = history.data[0]["version"]

    # 6. Restore — sections_count should match the snapshot at that version
    restored = section_restore(client, page_id=page_id, version=last_version)
    assert restored.ok

    # 7. Cleanup
    assert page_delete(client, page_id=page_id).ok
    assert profile_delete(client, profile_id=pid).ok
