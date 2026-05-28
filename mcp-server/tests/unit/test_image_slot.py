from elementor_mcp.core.image.slot import detect_image_slots, swap_image_in_section


def test_detect_finds_widget_image():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {},
        "elements": [{
            "id": "col1",
            "elType": "column",
            "settings": {},
            "elements": [{
                "id": "w1",
                "elType": "widget",
                "widgetType": "image",
                "settings": {"image": {"url": "http://x/old.png", "id": None}},
                "elements": [],
            }],
        }],
    }
    slots = detect_image_slots(section)
    assert len(slots) == 1
    assert slots[0]["widget_id"] == "w1"
    assert slots[0]["kind"] == "widget_image"
    assert slots[0]["current_url"] == "http://x/old.png"


def test_detect_finds_section_background_image():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {
            "background_background": "classic",
            "background_image": {"url": "http://x/bg.jpg", "id": None},
        },
        "elements": [],
    }
    slots = detect_image_slots(section)
    assert len(slots) == 1
    assert slots[0]["kind"] == "section_background"
    assert slots[0]["current_url"] == "http://x/bg.jpg"


def test_swap_replaces_widget_image_url():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {},
        "elements": [{
            "id": "col1",
            "elType": "column",
            "settings": {},
            "elements": [{
                "id": "w1",
                "elType": "widget",
                "widgetType": "image",
                "settings": {"image": {"url": "http://x/old.png", "id": None}},
                "elements": [],
            }],
        }],
    }
    out = swap_image_in_section(
        section,
        widget_id="w1",
        new_url="http://wp/new.png",
        new_id=99,
    )
    swapped = out["elements"][0]["elements"][0]["settings"]["image"]
    assert swapped["url"] == "http://wp/new.png"
    assert swapped["id"] == 99


def test_swap_replaces_section_background():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {
            "background_background": "classic",
            "background_image": {"url": "http://x/bg.jpg", "id": None},
        },
        "elements": [],
    }
    out = swap_image_in_section(
        section, widget_id=None, new_url="http://wp/bg.jpg", new_id=88, target="section_background",
    )
    assert out["settings"]["background_image"]["url"] == "http://wp/bg.jpg"
    assert out["settings"]["background_image"]["id"] == 88
