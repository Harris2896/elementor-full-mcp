from .diff import merge_diffs
from .passes import (
    pass1_colors,
    pass2_fonts,
    pass3_typography_sizes,
    pass4_layout,
    pass5_buttons,
    strip_tablet,
)


def normalize_section(section: dict, profile: dict) -> dict:
    """Apply six-pass normalizer to a section. Returns {section, diff}."""
    stripped = strip_tablet(section)
    tablet_count = stripped.pop("_tablet_stripped", 0)

    s, d1 = pass1_colors(stripped, profile)
    s, d2 = pass2_fonts(s, profile)
    s, d3 = pass3_typography_sizes(s, profile)
    s, d4 = pass4_layout(s, profile)
    s, d5 = pass5_buttons(s, profile)

    diff = merge_diffs(d1, d2, d3, d4, d5, {"tablet_stripped": tablet_count})
    return {"section": s, "diff": diff}
