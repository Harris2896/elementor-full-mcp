import re

import numpy as np

# colormath 3.0 uses np.asscalar() which was removed in numpy 2.0.
# Patch the alias on the numpy module before colormath imports it.
if not hasattr(np, "asscalar"):
    np.asscalar = lambda a: a.item()  # type: ignore[attr-defined]

# isort: off
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor, sRGBColor
# isort: on


_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def _to_lab(hex_color: str) -> LabColor:
    if not _HEX_RE.match(hex_color):
        raise ValueError(f"invalid hex color: {hex_color!r}")
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return convert_color(sRGBColor(r, g, b), LabColor)


def delta_e(a: str, b: str) -> float:
    """Perceptual color distance (ΔE2000) between two hex colors."""
    return float(delta_e_cie2000(_to_lab(a), _to_lab(b)))
