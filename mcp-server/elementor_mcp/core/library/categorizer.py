"""Heuristic category classifier for Elementor templates.

Given a template + already-extracted metadata, infer a category using a
priority list (first match wins). Used by the library indexer to assign
a category to each template.
"""

from __future__ import annotations


def categorize(template: dict, meta: dict) -> str:
    """Classify a template into one of the canonical category buckets.

    Args:
        template: Raw Elementor template dict (unused today; reserved for
            future heuristics that need to inspect raw structure).
        meta: Metadata previously produced by ``extract_metadata``.

    Returns:
        A category slug such as ``hero``, ``features``, ``pricing``, etc.
        Falls back to ``section-general`` when nothing matches.
    """
    widgets = set(meta.get("widgets_used") or [])
    columns_max = meta.get("columns_max", 0)
    image_count = meta.get("image_count", 0)

    if widgets & {"form", "shortcode-form"}:
        return "contact"
    if "price-table" in widgets:
        return "pricing"
    if "testimonial" in widgets:
        return "testimonial"
    if "nav-menu" in widgets:
        return "navbar"
    if "icon-box" in widgets and columns_max >= 3:
        return "features"
    if {"heading", "button"} <= widgets and columns_max <= 1:
        return "hero"
    if image_count >= 4 and not (widgets - {"image"}):
        return "social-proof"
    if {"heading", "button"} <= widgets:
        return "cta"
    return "section-general"
