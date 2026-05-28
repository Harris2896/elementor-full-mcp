import copy


def detect_image_slots(section: dict) -> list[dict]:
    """Walk a section and return a list of image-bearing slots.

    Each slot: {kind, widget_id, current_url, current_id}
    """
    slots: list[dict] = []

    # Section-level background image
    s = section.get("settings", {})
    if s.get("background_background") == "classic":
        bg = s.get("background_image") or {}
        if isinstance(bg, dict) and bg.get("url"):
            slots.append({
                "kind": "section_background",
                "widget_id": None,
                "current_url": bg.get("url"),
                "current_id": bg.get("id"),
            })

    def walk(node: dict) -> None:
        if node.get("elType") == "widget":
            wt = node.get("widgetType")
            ns = node.get("settings", {})
            if wt == "image":
                img = ns.get("image") or {}
                if isinstance(img, dict) and img.get("url"):
                    slots.append({
                        "kind": "widget_image",
                        "widget_id": node.get("id"),
                        "current_url": img.get("url"),
                        "current_id": img.get("id"),
                    })
        for child in node.get("elements", []):
            walk(child)

    for el in section.get("elements", []):
        walk(el)

    return slots


def swap_image_in_section(
    section: dict,
    *,
    widget_id: str | None,
    new_url: str,
    new_id: int,
    target: str = "widget_image",
) -> dict:
    """Return a deep copy of `section` with the named image slot replaced."""
    out = copy.deepcopy(section)

    if target == "section_background":
        s = out.setdefault("settings", {})
        s["background_image"] = {"url": new_url, "id": new_id}
        return out

    # widget_image: walk and patch matching widget id
    def walk(node: dict) -> None:
        if node.get("elType") == "widget" and node.get("widgetType") == "image" and node.get("id") == widget_id:
            node.setdefault("settings", {})["image"] = {"url": new_url, "id": new_id}
            return
        for child in node.get("elements", []):
            walk(child)

    for el in out.get("elements", []):
        walk(el)

    return out
