import re

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COLOR_KEY_RE = re.compile(r"(_color$|^background_color$)")


def extract_metadata(template: dict) -> dict:
    """Walk a template JSON and return structural metadata."""
    widgets: set[str] = set()
    colors: set[str] = set()
    fonts: set[str] = set()
    image_count = 0
    has_form = 0
    has_carousel = 0
    has_video = 0
    columns_max = 0

    def visit_section(section: dict) -> None:
        nonlocal columns_max
        cols = [e for e in section.get("elements", []) if e.get("elType") == "column"]
        if cols:
            columns_max = max(columns_max, len(cols))
        for child in section.get("elements", []):
            visit(child)

    def visit(node: dict) -> None:
        nonlocal image_count, has_form, has_carousel, has_video
        el_type = node.get("elType")
        if el_type == "widget":
            wt = node.get("widgetType") or ""
            widgets.add(wt)
            if wt == "image":
                image_count += 1
            if wt in {"form", "shortcode-form"}:
                has_form = 1
            if "carousel" in wt or wt == "image-carousel":
                has_carousel = 1
            if "video" in wt:
                has_video = 1
        for k, v in (node.get("settings") or {}).items():
            if isinstance(v, str):
                if _COLOR_KEY_RE.search(k) and _COLOR_RE.match(v):
                    colors.add(v.upper())
                if k == "typography_font_family" and v:
                    fonts.add(v)
        for child in node.get("elements", []) or []:
            visit(child)

    for section in template.get("content", []):
        visit_section(section)
        visit(section)

    return {
        "widgets_used": sorted(widgets),
        "columns_max":  columns_max,
        "image_count":  image_count,
        "has_form":     has_form,
        "has_carousel": has_carousel,
        "has_video":    has_video,
        "dominant_colors": sorted(colors),
        "font_families":   sorted(fonts),
    }
